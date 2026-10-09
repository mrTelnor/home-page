"""Вики: проверка сертификата сервера при подключении к базе знаний (QA, задача 17).

В Supabase и во внешнюю сеть тесты не ходят. Вместо пулера — локальный сервер на
127.0.0.1, который отвечает на SSLRequest протокола Postgres ('S', затем TLS-рукопожатие),
а после удачного рукопожатия читает StartupMessage и отвечает ошибкой с меткой: довести
подключение до конца без настоящего Postgres нельзя, но по метке видно, что TLS пройден.
Подключается настоящий engine SQLAlchemy/asyncpg из `wiki_db.get_wiki_engine()`.

Сертификаты и закрытые ключи создаются на лету во временном каталоге pytest
и в репозиторий не попадают.
"""
import datetime
import hashlib
import logging
import socket
import ssl
import struct
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from httpx import AsyncClient

from app.core import wiki_db
from app.core.config import settings
from tests.test_wiki import PROTECTED_PATHS

DB_USER = "wiki_reader.projectref"
DB_PASSWORD = "qa-Pa55w0rd-do-not-leak"
# Имя, на которое выписан «правильный» сертификат сервера: как и на проде, в строке
# подключения стоит имя хоста, а не IP
SERVER_HOST = "localhost"
# Отпечаток SHA-256 корневого сертификата Supabase Root 2021 CA — из плана архитектора,
# сверен Никитой с файлом из Dashboard (задача 17, шаг 0)
SUPABASE_ROOT_SHA256 = "80:70:25:AD:50:D4:ED:21:9D:2C:9C:7D:29:9C:00:4F:82:4E:B0:0C:F7:F6:5A:FE:F6:07:D0:7B:72:E6:CA:FA"
# Текст ошибки, которой сервер-заглушка отвечает после удачного рукопожатия
TLS_PASSED_MARK = "qa-fake-postgres-tls-handshake-passed"
# Код запроса SSLRequest протокола Postgres
SSL_REQUEST = struct.pack("!II", 8, 80877103)


# --- Сертификаты, создаваемые в тесте ---


@dataclass
class Issued:
    cert: x509.Certificate
    key: ec.EllipticCurvePrivateKey


def _issue(
    common_name: str,
    *,
    issuer: Issued | None = None,
    is_ca: bool = False,
    key_usage: bool = True,
    dns_names: tuple[str, ...] = (),
) -> Issued:
    """Выписать сертификат: без `issuer` — самоподписанный."""
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    signing_key = issuer.key if issuer else key
    issuer_name = issuer.cert.subject if issuer else subject
    issuer_public_key = issuer.key.public_key() if issuer else key.public_key()
    now = datetime.datetime.now(datetime.UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(hours=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=is_ca, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_public_key), critical=False)
    )
    if key_usage:
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=not is_ca,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=is_ca,
                crl_sign=is_ca,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    if dns_names:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(name) for name in dns_names]), critical=False
        )
    return Issued(cert=builder.sign(signing_key, hashes.SHA256()), key=key)


def _pem(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


@dataclass
class ServerIdentity:
    """Файлы для сервера-заглушки: цепочка (лист и промежуточные) и закрытый ключ."""

    chain_file: Path
    key_file: Path


@dataclass
class Pki:
    # Корневой сертификат «своего» CA — им в тестах подменяется WIKI_CA_FILE
    ca_file: Path
    # Свой CA, имя сервера совпадает
    good: ServerIdentity
    # Свой CA, сертификат выписан на другое имя
    wrong_name: ServerIdentity
    # Сертификат на верное имя, но от чужого CA
    foreign_ca: ServerIdentity
    # Самоподписанный сертификат на верное имя
    self_signed: ServerIdentity
    # Как у пулера Supabase: лист ← промежуточный CA без расширения keyUsage ← корневой;
    # сервер отдаёт промежуточный сам
    supabase_like: ServerIdentity


@pytest.fixture(scope="module")
def pki(tmp_path_factory) -> Pki:
    directory = tmp_path_factory.mktemp("wiki-tls")

    def save(name: str, leaf: Issued, *intermediates: Issued) -> ServerIdentity:
        chain_file = directory / f"{name}.crt"
        chain_file.write_bytes(b"".join(_pem(item.cert) for item in (leaf, *intermediates)))
        key_file = directory / f"{name}.key"
        key_file.write_bytes(
            leaf.key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        return ServerIdentity(chain_file=chain_file, key_file=key_file)

    own_ca = _issue("QA Own Root CA", is_ca=True)
    foreign_ca = _issue("QA Foreign Root CA", is_ca=True)
    intermediate = _issue("QA Own Intermediate CA", issuer=own_ca, is_ca=True, key_usage=False)

    ca_file = directory / "own-root-ca.crt"
    ca_file.write_bytes(_pem(own_ca.cert))

    return Pki(
        ca_file=ca_file,
        good=save("good", _issue(SERVER_HOST, issuer=own_ca, dns_names=(SERVER_HOST,))),
        wrong_name=save("wrong-name", _issue("other.example", issuer=own_ca, dns_names=("other.example",))),
        foreign_ca=save("foreign-ca", _issue(SERVER_HOST, issuer=foreign_ca, dns_names=(SERVER_HOST,))),
        self_signed=save("self-signed", _issue(SERVER_HOST, dns_names=(SERVER_HOST,))),
        supabase_like=save(
            "supabase-like",
            _issue(SERVER_HOST, issuer=intermediate, dns_names=(SERVER_HOST,)),
            intermediate,
        ),
    )


# --- Сервер-заглушка: SSLRequest → 'S' → TLS ---


def _read_exact(conn: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            break
        data += chunk
    return data


class FakePostgresTLSServer:
    """Слушает 127.0.0.1 в отдельном потоке и запоминает, чем кончилось каждое подключение."""

    def __init__(self, identity: ServerIdentity | None):
        # identity=None — сервер отказывает в TLS (отвечает 'N' на SSLRequest)
        self._context: ssl.SSLContext | None = None
        if identity is not None:
            self._context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self._context.load_cert_chain(certfile=identity.chain_file, keyfile=identity.key_file)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self._sock.settimeout(0.2)
        self.port: int = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        # Сколько клиентов прислали SSLRequest
        self.ssl_requests = 0
        # Исход каждого TLS-рукопожатия: "ok" либо имя исключения на стороне сервера
        self.handshakes: list[str] = []
        # Имена пользователей из StartupMessage, дошедших до сервера внутри TLS
        self.startup_users: list[str] = []
        # Байты, которые клиент прислал открытым текстом после отказа сервера в TLS
        self.plaintext_after_refusal = b""

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self._sock.close()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with conn:
                conn.settimeout(5)
                try:
                    self._handle(conn)
                except OSError:
                    # Клиент оборвал соединение — исход уже записан
                    pass

    def _handle(self, conn: socket.socket) -> None:
        if _read_exact(conn, len(SSL_REQUEST)) != SSL_REQUEST:
            return
        self.ssl_requests += 1
        if self._context is None:
            conn.sendall(b"N")
            self.plaintext_after_refusal += conn.recv(4096)
            return
        conn.sendall(b"S")
        try:
            tls = self._context.wrap_socket(conn, server_side=True)
        except OSError as exc:
            self.handshakes.append(type(exc).__name__)
            return
        self.handshakes.append("ok")
        with tls:
            (length,) = struct.unpack("!I", _read_exact(tls, 4))
            payload = _read_exact(tls, length - 4)
            # StartupMessage: версия протокола, затем пары «имя\0значение\0»
            fields = payload[4:].split(b"\x00")
            params = dict(zip(fields[::2], fields[1::2], strict=False))
            self.startup_users.append(params.get(b"user", b"").decode())
            body = b"SFATAL\x00VFATAL\x00C28000\x00M" + TLS_PASSED_MARK.encode() + b"\x00\x00"
            tls.sendall(b"E" + struct.pack("!I", len(body) + 4) + body)


@pytest.fixture
def tls_server():
    """Фабрика серверов-заглушек; все запущенные останавливаются после теста."""
    servers: list[FakePostgresTLSServer] = []

    def start(identity: ServerIdentity | None) -> FakePostgresTLSServer:
        server = FakePostgresTLSServer(identity)
        server.start()
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.stop()


def _dsn(port: int, host: str = SERVER_HOST) -> str:
    return f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{host}:{port}/postgres"


@pytest.fixture
async def wiki_points_to(monkeypatch):
    """Настоящий engine вики смотрит на сервер-заглушку; при `ca_file` подменяется WIKI_CA_FILE."""

    def configure(server: FakePostgresTLSServer, *, ca_file: Path | None = None, host: str = SERVER_HOST) -> str:
        monkeypatch.setattr(wiki_db, "_engine", None)
        monkeypatch.setattr(settings, "wiki_database_url", _dsn(server.port, host))
        if ca_file is not None:
            monkeypatch.setattr(wiki_db, "WIKI_CA_FILE", ca_file)
        return settings.wiki_database_url

    yield configure
    await wiki_db.dispose_wiki_engine()


async def _connect_error() -> BaseException:
    """Подключиться настоящим engine вики и вернуть исключение: до конца подключение дойти не может."""
    engine = wiki_db.get_wiki_engine()
    with pytest.raises(Exception) as exc_info:  # тип исключения проверяет вызывающий
        async with engine.connect():
            pass
    return exc_info.value


def _error_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def _assert_certificate_rejected(exc: BaseException, server: FakePostgresTLSServer) -> ssl.SSLCertVerificationError:
    """Отказ вызван именно проверкой сертификата, и внутрь TLS клиент ничего не отправил."""
    verify_errors = [item for item in _error_chain(exc) if isinstance(item, ssl.SSLCertVerificationError)]
    assert verify_errors, f"ожидалась ошибка проверки сертификата, получено: {exc!r}"
    assert server.ssl_requests >= 1
    assert "ok" not in server.handshakes
    assert server.startup_users == []
    return verify_errors[0]


def _assert_tls_passed(exc: BaseException, server: FakePostgresTLSServer) -> None:
    """Рукопожатие прошло: сервер получил StartupMessage внутри TLS и ответил своей ошибкой."""
    assert not any(isinstance(item, ssl.SSLError) for item in _error_chain(exc)), repr(exc)
    assert TLS_PASSED_MARK in str(exc)
    assert server.handshakes == ["ok"]
    assert server.startup_users == [DB_USER]


# --- Контекст из рабочего кода: что именно в нём настроено ---


def test_context_trusts_only_supabase_root_ca():
    context = wiki_db.build_wiki_ssl_context()

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    # Строгая проверка X.509 снята: с ней цепочка Supabase отклоняется
    assert not context.verify_flags & ssl.VERIFY_X509_STRICT
    # Системное хранилище не подключено: в контексте ровно один сертификат
    assert context.cert_store_stats() == {"x509": 1, "crl": 0, "x509_ca": 1}
    (ca_der,) = context.get_ca_certs(binary_form=True)
    fingerprint = hashlib.sha256(ca_der).hexdigest().upper()
    assert ":".join(fingerprint[i : i + 2] for i in range(0, len(fingerprint), 2)) == SUPABASE_ROOT_SHA256
    (ca_info,) = context.get_ca_certs()
    assert (("commonName", "Supabase Root 2021 CA"),) in ca_info["subject"]


def test_ca_file_is_single_certificate_inside_app_package():
    """Файл лежит внутри каталога app/ — в образ backend попадает только он (COPY app/ app/)."""
    app_dir = Path(wiki_db.__file__).resolve().parent.parent

    assert wiki_db.WIKI_CA_FILE.is_file()
    assert app_dir in wiki_db.WIKI_CA_FILE.parents
    content = wiki_db.WIKI_CA_FILE.read_bytes()
    assert content.count(b"-----BEGIN CERTIFICATE-----") == 1
    # Сертификат публичный; закрытого ключа рядом быть не должно
    assert b"PRIVATE KEY" not in content


def test_context_is_built_from_wiki_ca_file(monkeypatch, pki: Pki):
    """Подмена WIKI_CA_FILE меняет доверенный CA — на этом держатся тесты ниже."""
    monkeypatch.setattr(wiki_db, "WIKI_CA_FILE", pki.ca_file)

    context = wiki_db.build_wiki_ssl_context()

    (ca_info,) = context.get_ca_certs()
    assert (("commonName", "QA Own Root CA"),) in ca_info["subject"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


# --- Отказы: рабочая настройка (доверие только Supabase Root 2021 CA) ---


@pytest.mark.parametrize("identity_name", ["self_signed", "foreign_ca", "good"])
async def test_production_context_rejects_any_other_certificate(tls_server, wiki_points_to, pki: Pki, identity_name: str):
    """WIKI_CA_FILE не подменён: самоподписанный и выданный любым другим CA сертификат не проходит."""
    server = tls_server(getattr(pki, identity_name))
    wiki_points_to(server)

    error = await _connect_error()

    _assert_certificate_rejected(error, server)


# --- Отказы и успех: свой CA подставлен вместо WIKI_CA_FILE ---


async def test_self_signed_certificate_is_rejected(tls_server, wiki_points_to, pki: Pki):
    server = tls_server(pki.self_signed)
    wiki_points_to(server, ca_file=pki.ca_file)

    error = await _connect_error()

    _assert_certificate_rejected(error, server)


async def test_certificate_from_foreign_ca_is_rejected(tls_server, wiki_points_to, pki: Pki):
    server = tls_server(pki.foreign_ca)
    wiki_points_to(server, ca_file=pki.ca_file)

    error = await _connect_error()

    _assert_certificate_rejected(error, server)


async def test_own_ca_but_wrong_hostname_is_rejected(tls_server, wiki_points_to, pki: Pki):
    """Цепочка верная, но сертификат выписан на другое имя."""
    server = tls_server(pki.wrong_name)
    wiki_points_to(server, ca_file=pki.ca_file)

    error = await _connect_error()

    verify_error = _assert_certificate_rejected(error, server)
    assert "hostname mismatch" in str(verify_error).lower()


async def test_own_ca_but_ip_instead_of_hostname_is_rejected(tls_server, wiki_points_to, pki: Pki):
    """В строке подключения IP вместо имени: сертификат выписан на имя, проверка имени не проходит."""
    server = tls_server(pki.good)
    wiki_points_to(server, ca_file=pki.ca_file, host="127.0.0.1")

    error = await _connect_error()

    _assert_certificate_rejected(error, server)


async def test_own_ca_and_right_hostname_passes_handshake(tls_server, wiki_points_to, pki: Pki):
    server = tls_server(pki.good)
    wiki_points_to(server, ca_file=pki.ca_file)

    error = await _connect_error()

    _assert_tls_passed(error, server)


async def test_chain_like_supabase_passes_handshake(tls_server, wiki_points_to, pki: Pki):
    """Промежуточный CA без keyUsage, отданный сервером, — как у пулера Supabase: в хранилище только корневой."""
    server = tls_server(pki.supabase_like)
    wiki_points_to(server, ca_file=pki.ca_file)

    error = await _connect_error()

    _assert_tls_passed(error, server)


async def test_chain_like_supabase_needs_strict_flag_off(tls_server, wiki_points_to, monkeypatch, pki: Pki):
    """Контроль к тесту выше: та же цепочка со строгой проверкой X.509 отклоняется.

    Значит, снятый в `build_wiki_ssl_context` флаг — не формальность: с контекстом,
    где строгая проверка включена (`ssl.create_default_context()` на Python 3.13),
    подключение не прошло бы.
    """
    original = wiki_db.build_wiki_ssl_context

    def strict_context() -> ssl.SSLContext:
        context = original()
        context.verify_flags |= ssl.VERIFY_X509_STRICT
        return context

    monkeypatch.setattr(wiki_db, "build_wiki_ssl_context", strict_context)
    server = tls_server(pki.supabase_like)
    wiki_points_to(server, ca_file=pki.ca_file)

    error = await _connect_error()

    verify_error = _assert_certificate_rejected(error, server)
    assert "key usage" in str(verify_error).lower()


async def test_server_refusing_tls_gets_no_plaintext(tls_server, wiki_points_to, pki: Pki):
    """Сервер отвечает 'N' на SSLRequest: подключение рвётся, открытым текстом клиент не идёт."""
    server = tls_server(None)
    wiki_points_to(server, ca_file=pki.ca_file)

    error = await _connect_error()

    assert TLS_PASSED_MARK not in str(error)
    assert server.ssl_requests == 1
    assert server.plaintext_after_refusal == b""


# --- Сбой проверки сертификата для вики то же, что недоступная база: 503 и unavailable ---


def _assert_no_secret(text: str) -> None:
    assert DB_PASSWORD not in text
    assert settings.wiki_database_url not in text


@pytest.fixture
def untrusted_server(tls_server, wiki_points_to, pki: Pki) -> FakePostgresTLSServer:
    """Рабочая настройка (WIKI_CA_FILE не подменён) и сервер с самоподписанным сертификатом."""
    server = tls_server(pki.self_signed)
    wiki_points_to(server)
    return server


async def test_untrusted_certificate_protected_returns_503(
    admin_client: AsyncClient, untrusted_server: FakePostgresTLSServer, caplog
):
    caplog.set_level(logging.DEBUG)

    for path in PROTECTED_PATHS:
        response = await admin_client.get(path)

        assert response.status_code == 503, f"{path}: {response.status_code}"
        assert response.json() == {"detail": "Wiki database is unavailable"}
        _assert_no_secret(response.text)

    # Причина в логе — именно проверка сертификата, а не что-то другое
    assert "Wiki database request failed" in caplog.text
    assert "CERTIFICATE_VERIFY_FAILED" in caplog.text
    _assert_no_secret(caplog.text)
    assert untrusted_server.ssl_requests == len(PROTECTED_PATHS)
    assert "ok" not in untrusted_server.handshakes
    assert untrusted_server.startup_users == []


async def test_untrusted_certificate_health_is_200_unavailable(
    client: AsyncClient, untrusted_server: FakePostgresTLSServer, caplog
):
    caplog.set_level(logging.DEBUG)

    response = await client.get("/api/wiki/health")

    assert response.status_code == 200
    assert response.json() == {"status": "unavailable"}
    assert "Wiki health check failed" in caplog.text
    assert "CERTIFICATE_VERIFY_FAILED" in caplog.text
    _assert_no_secret(response.text)
    _assert_no_secret(caplog.text)
    assert untrusted_server.startup_users == []


# --- Файл сертификата отсутствует или испорчен: тоже 503 и unavailable, а не 500 ---


@pytest.fixture(params=["missing", "empty", "garbage", "truncated"])
def broken_ca_file(request, monkeypatch, tmp_path, tls_server, pki: Pki) -> FakePostgresTLSServer:
    """WIKI_CA_FILE указывает на негодный файл; сервер при этом предъявляет «хороший» сертификат."""
    ca_file = tmp_path / "ca.crt"
    if request.param == "empty":
        ca_file.write_bytes(b"")
    elif request.param == "garbage":
        ca_file.write_text("это не сертификат\n", encoding="utf-8")
    elif request.param == "truncated":
        content = pki.ca_file.read_bytes()
        ca_file.write_bytes(content[: len(content) // 2])
    server = tls_server(pki.good)
    monkeypatch.setattr(wiki_db, "_engine", None)
    monkeypatch.setattr(settings, "wiki_database_url", _dsn(server.port))
    monkeypatch.setattr(wiki_db, "WIKI_CA_FILE", ca_file)
    yield server
    wiki_db._engine = None


async def test_broken_ca_file_protected_returns_503(
    admin_client: AsyncClient, broken_ca_file: FakePostgresTLSServer, caplog
):
    caplog.set_level(logging.DEBUG)

    for path in PROTECTED_PATHS:
        response = await admin_client.get(path)

        assert response.status_code == 503, f"{path}: {response.status_code}"
        assert response.json() == {"detail": "Wiki database is unavailable"}
        _assert_no_secret(response.text)

    assert "Wiki database request failed" in caplog.text
    _assert_no_secret(caplog.text)
    # Без годного CA engine не создаётся: до сервера клиент не доходит вовсе
    assert wiki_db._engine is None
    assert broken_ca_file.ssl_requests == 0


async def test_broken_ca_file_health_is_200_unavailable(
    client: AsyncClient, broken_ca_file: FakePostgresTLSServer, caplog
):
    caplog.set_level(logging.DEBUG)

    response = await client.get("/api/wiki/health")

    assert response.status_code == 200
    assert response.json() == {"status": "unavailable"}
    assert "Wiki health check failed" in caplog.text
    _assert_no_secret(response.text)
    _assert_no_secret(caplog.text)
    assert broken_ca_file.ssl_requests == 0


def test_broken_ca_file_does_not_matter_while_wiki_is_disabled(monkeypatch, tmp_path):
    """Вики выключена — файл сертификата не читается, backend от него не зависит."""
    monkeypatch.setattr(wiki_db, "_engine", None)
    monkeypatch.setattr(wiki_db, "WIKI_CA_FILE", tmp_path / "net-takogo.crt")
    assert settings.wiki_database_url == ""

    with pytest.raises(wiki_db.WikiDisabledError):
        wiki_db.get_wiki_engine()
