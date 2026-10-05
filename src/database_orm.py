#python
import os
from datetime import datetime, timedelta
from pathlib import Path
#terceros
from dateutil.relativedelta import relativedelta
from sqlalchemy import event
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
    relationship,
)
from sqlalchemy import (
    String,
    Integer,
    Float,
    Numeric,
    ForeignKey,
    DateTime,
    Column,
    Boolean,
    create_engine,
    text,
    Text,

)
#locales

#conxion a la base de datos
# En app empaquetada FLET_APP_STORAGE_DATA es persistente entre actualizaciones.
# En dev, si no existe, se usa la carpeta local storage/data.
_DIR_DATOS = Path(os.environ.get("FLET_APP_STORAGE_DATA") or (Path.cwd() / "storage" / "data"))
_DIR_DATOS.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{(_DIR_DATOS / 'gestion_pagos.db').as_posix()}", echo=False)

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()

# relacion entre la conexion y los modelos
SessionLocal = sessionmaker(engine)
session = SessionLocal()

class Base(DeclarativeBase):
    pass

class Miembro(Base):
    __tablename__ = "miembros"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    nombre = Column(String(50), nullable=False)
    fecha_registro = Column(DateTime(), nullable=False, default=datetime.now())
    fecha_vencimiento = Column(DateTime())
    es_prueba = Column(Boolean(), default=True) # empieza como prueba por defecto
    tiempo_prueba_dias = Column(Integer(), default=0) # duracion de la prueba en dias, por defecto 1 dia

    historial_pagos = relationship("HistorialPago", cascade="all, delete-orphan", back_populates="_miembro")
    cronogramas = relationship("Cronograma", cascade="all, delete-orphan", back_populates="_miembro")

    def __str__(self):
        return self.nombre
    
class Configuracion(Base):
    __tablename__ = "configuraciones"

    clave = Column(String(55), primary_key=True)
    valor = Column(String(55), nullable=False)

    def __str__(self):
        return f"{self.clave}: {self.valor}"


class HistorialPago(Base):
    __tablename__ = "historial_pagos"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    miembro_id = Column(Integer(), ForeignKey("miembros.id"))
    fecha_pago = Column(DateTime(), nullable=False)
    monto = Column(Numeric(precision=10, scale=2), nullable=False)
    meses_abonados = Column(Integer(), default=1)

    _miembro = relationship("Miembro", back_populates="historial_pagos")

    def __str__(self):
        return f"Pago de {self.monto} el {self.fecha_pago} por {self.meses_abonados} meses"


class Cronograma(Base):
    __tablename__ = "cronogramas"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    miembro_id = Column(Integer(), ForeignKey("miembros.id"))
    dia_semana = Column(Integer(), nullable=False)
    fecha = Column(DateTime(), nullable=True)
    semana = Column(Integer(), nullable=True)
    descripcion = Column(Text, nullable=True)
    repetir_semanal = Column(Boolean(), default=True)

    _miembro = relationship("Miembro", back_populates="cronogramas")

    def __str__(self):
        return f"Día {self.dia_semana}: {self.descripcion}"


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def _ultimo_pago(miembro_id: int, session: Session) -> HistorialPago | None:
    """
    Retorna el último pago registrado para un miembro.
    ---
    Entrada:
        miembro_id (int): ID del miembro.
        session (Session): Sesión activa de SQLAlchemy.
    Salida:
        HistorialPago | None: Último pago o None si no hay registros.
    """
    return (
        session.query(HistorialPago)
        .filter_by(miembro_id=miembro_id)
        .order_by(HistorialPago.fecha_pago.desc())
        .first()
    )


def _inicio_ciclo_pago(miembro: Miembro) -> datetime:
    """
    Retorna la fecha en que empieza a contar el ciclo de pago.
    Si el miembro tiene días de prueba, se suma ese período a la fecha de registro.
    ---
    Entrada:
        miembro (Miembro): Instancia del miembro.
    Salida:
        datetime: Fecha de inicio del ciclo de pago.
    """
    if miembro.es_prueba and miembro.tiempo_prueba_dias > 0:
        return miembro.fecha_registro + timedelta(days=miembro.tiempo_prueba_dias)
    return miembro.fecha_registro


def _fecha_vencimiento(miembro: Miembro, session: Session) -> datetime:
    """
    Calcula la fecha de vencimiento acumulando todos los pagos del miembro.
    Cada pago extiende desde max(vencimiento_actual, fecha_pago) + meses_abonados.
    Si no hay pagos, toma la fecha de inicio del ciclo + 1 mes.
    ---
    Entrada:
        miembro (Miembro): Instancia del miembro.
        session (Session): Sesión activa de SQLAlchemy.
    Salida:
        datetime: Fecha de vencimiento calculada.
    """
    # Override manual: si se fijó una fecha de vencimiento, tiene prioridad
    if miembro.fecha_vencimiento is not None:
        return miembro.fecha_vencimiento

    inicio = _inicio_ciclo_pago(miembro)
    ahora = datetime.now()

    # Si todavía está en período de prueba, la fecha de vencimiento es al terminar la prueba
    if miembro.es_prueba and miembro.tiempo_prueba_dias > 0 and ahora < inicio:
        return inicio

    # Acumular todos los pagos ordenados cronológicamente
    pagos = (
        session.query(HistorialPago)
        .filter_by(miembro_id=miembro.id)
        .order_by(HistorialPago.fecha_pago.asc())
        .all()
    )

    if not pagos:
        # Sin pagos: vence al finalizar el inicio del ciclo (sin mes regalado)
        return inicio

    vencimiento = inicio
    for pago in pagos:
        base = max(vencimiento, pago.fecha_pago)
        vencimiento = base + relativedelta(months=pago.meses_abonados)

    return vencimiento


def _calcular_vencimiento(miembro: Miembro, session: Session) -> int:
    """
    Calcula cuántos meses completos está vencido el pago del miembro.
    0 significa que está al día.
    ---
    Entrada:
        miembro (Miembro): Instancia del miembro.
        session (Session): Sesión activa de SQLAlchemy.
    Salida:
        int: Cantidad de meses vencido (0 = al día).
    """
    ahora = datetime.now()

    # Si está en prueba (y no hay override manual), no está vencido
    inicio = _inicio_ciclo_pago(miembro)
    if (miembro.fecha_vencimiento is None and miembro.es_prueba
            and miembro.tiempo_prueba_dias > 0 and ahora < inicio):
        return 0

    vencimiento = _fecha_vencimiento(miembro, session)

    if ahora <= vencimiento:
        return 0

    diff = relativedelta(ahora, vencimiento)
    meses = diff.months + (diff.years * 12)

    tiene_pagos = (
        session.query(HistorialPago)
        .filter_by(miembro_id=miembro.id)
        .count()
    ) > 0
    if not tiene_pagos:
        meses = max(meses, 1)

    return meses


def _esta_vencido(miembro: Miembro, session: Session) -> bool:
    """
    Verifica si el miembro tiene el pago vencido.
    ---
    Entrada:
        miembro (Miembro): Instancia del miembro.
        session (Session): Sesión activa de SQLAlchemy.
    Salida:
        bool: True si está vencido, False si está al día.
    """
    return _calcular_vencimiento(miembro, session) > 0


def _dias_restantes(miembro: Miembro, session: Session) -> int:
    """
    Retorna la cantidad de días que faltan para el vencimiento.
    Si ya está vencido, retorna 0.
    ---
    Entrada:
        miembro (Miembro): Instancia del miembro.
        session (Session): Sesión activa de SQLAlchemy.
    Salida:
        int: Días restantes (0 si ya venció).
    """
    if _esta_vencido(miembro, session):
        return 0

    vencimiento = _fecha_vencimiento(miembro, session)
    diff = vencimiento - datetime.now()
    return max(0, diff.days)


def _dias_pasados(miembro: Miembro, session: Session) -> int:
    """
    Retorna la cantidad de días que pasaron desde el vencimiento.
    Si no está vencido, retorna 0.
    ---
    Entrada:
        miembro (Miembro): Instancia del miembro.
        session (Session): Sesión activa de SQLAlchemy.
    Salida:
        int: Días transcurridos desde el vencimiento (0 si no venció).
    """
    if not _esta_vencido(miembro, session):
        return 0

    vencimiento = _fecha_vencimiento(miembro, session)
    diff = datetime.now() - vencimiento
    return max(0, diff.days)


def _estado_semaforo(miembro: Miembro, session: Session) -> str:
    """
    Retorna el estado del semáforo para la tarjeta del miembro.
    ---
    Entrada:
        miembro (Miembro): Instancia del miembro.
        session (Session): Sesión activa de SQLAlchemy.
    Salida:
        str: "vencido" = rojo, "en_prueba" = amarillo, "al_dia" = verde.
    """
    ahora = datetime.now()
    inicio = _inicio_ciclo_pago(miembro)

    if (miembro.fecha_vencimiento is None and miembro.es_prueba
            and miembro.tiempo_prueba_dias > 0 and ahora < inicio):
        return "en_prueba"

    tiene_pagos = (
        session.query(HistorialPago)
        .filter_by(miembro_id=miembro.id)
        .count()
    ) > 0

    if _esta_vencido(miembro, session) or (not tiene_pagos and miembro.fecha_vencimiento is None):
        return "vencido"

    return "al_dia"


def _leer_configuracion(clave: str, session: Session, default: str = "") -> str:
    """
    Lee un valor de configuración de la base de datos.
    ---
    Entrada:
        clave (str): Clave de configuración (ej: "precio_mensual").
        session (Session): Sesión activa de SQLAlchemy.
        default (str): Valor por defecto si no existe la clave.
    Salida:
        str: Valor de la configuración o default si no existe.
    """
    config = session.query(Configuracion).filter_by(clave=clave).first()
    return config.valor if config else default


def _guardar_configuracion(clave: str, valor: str, session: Session) -> None:
    """
    Guarda o actualiza un valor de configuración en la base de datos.
    Si la clave ya existe, sobrescribe el valor. Si no, la crea.
    ---
    Entrada:
        clave (str): Clave de configuración (ej: "precio_mensual").
        valor (str): Valor a guardar.
        session (Session): Sesión activa de SQLAlchemy.
    Salida:
        None
    """
    config = session.query(Configuracion).filter_by(clave=clave).first()
    if config:
        config.valor = valor
    else:
        session.add(Configuracion(clave=clave, valor=valor))
    session.commit()


def _generar_status_text(miembro: Miembro, session: Session) -> str:
    """
    Genera el texto descriptivo del estado para mostrar en la tarjeta del miembro.
    ---
    Entrada:
        miembro (Miembro): Instancia del miembro.
        session (Session): Sesión activa de SQLAlchemy.
    Salida:
        str: Texto descriptivo del estado (ej: "Vencido - Debe 2 meses ($6000)").
    """
    estado = _estado_semaforo(miembro, session)

    if estado == "vencido":
        meses = _calcular_vencimiento(miembro, session)
        if meses == 0:
            return "Vencido - Pendiente de pago"
        precio = float(_leer_configuracion("precio_mensual", session, "3000"))
        deuda = meses * precio
        return f"Vencido - Debe {meses} meses (${deuda:.0f})"

    if estado == "en_prueba":
        inicio = _inicio_ciclo_pago(miembro)
        dias = (inicio - datetime.now()).days
        return f"Prueba - {dias} días restantes"

    # al_dia
    venc = _fecha_vencimiento(miembro, session)
    return f"Cuota al día - Vence el {venc.strftime('%d %b %Y')}"


def _inicializar_db():
    """
    Crea el directorio de la base de datos si no existe y
    las tablas necesarias solo si no están creadas aún.
    ---
    create_all() ya tiene checkfirst=True por defecto:
    no recrea tablas existentes.
    """
    _DIR_DATOS.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(cronogramas)"))
        columnas = [row[1] for row in result]
        if "semana" not in columnas:
            conn.execute(text("ALTER TABLE cronogramas ADD COLUMN semana INTEGER"))
            conn.commit()


# Inicializar BD automáticamente al importar el módulo
_inicializar_db()
