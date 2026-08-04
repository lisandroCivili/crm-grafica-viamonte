"""Script para popular la base de datos con datos de ejemplo realistas.

Crea:
- 2 clientes
- Stock (artículos de papel)
- 2 presupuestos: uno con 2 ítems (mismo cliente, mismo presupuesto) y otro con 1
- 3 trabajos en estado Aprobado (conversión de presupuestos)
- Gastos asociados a trabajos
- Cheques
- Movimientos (pagos)

USO:
    python poblar_base_ejemplo.py

ADVERTENCIA: Borra TODOS los datos anteriores y vuelve a crear la BD desde cero.
"""
from decimal import Decimal
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from database import SessionLocal, engine, Base
import models
from money import Q2, Q3

NOMBRES_USUARIOS_REALES = ("facundo", "marcos", "lucio")


def _es_base_real() -> bool:
    """¿Esta base tiene alguno de los usuarios reales del taller?

    Este script borra TODA la base (drop_all). Si por error se corre apuntando
    a la base de producción en vez de a la del demo, este chequeo frena antes
    de perder datos reales.
    """
    db = SessionLocal()
    try:
        return db.query(models.Usuario).filter(
            models.Usuario.nombre.in_(NOMBRES_USUARIOS_REALES)
        ).first() is not None
    finally:
        db.close()


def crear_datos_ejemplo():
    """Crea todos los datos de ejemplo desde cero."""

    if _es_base_real():
        print("❌ Esta base tiene usuarios reales (facundo/marcos/lucio).")
        print("   Este script NO se ejecuta acá: borraría datos de producción.")
        return

    print("🗑️  Limpiando base de datos anterior...")
    # Borra todas las tablas y las recrea
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    db = SessionLocal()

    try:
        print("👥 Creando clientes...")
        # Cliente 1: Empresa pequeña
        cliente1 = models.Cliente(
            nombre_completo="Juan García",
            nombre_empresa="Gráfica García S.A.",
            dni_cuit="20-12345678-9",
            telefono="011-4555-0123",
            frecuencia_recompra_dias=30
        )
        db.add(cliente1)
        db.flush()

        # Cliente 2: Negocio local
        cliente2 = models.Cliente(
            nombre_completo="María López",
            nombre_empresa="Impresos López",
            dni_cuit="27-98765432-1",
            telefono="011-4666-0456",
            frecuencia_recompra_dias=45
        )
        db.add(cliente2)
        db.flush()

        print("📦 Creando stock...")
        # Artículos de stock
        papel_a4 = models.ArticuloStock(
            nombre="Papel A4 80 gr blanco",
            categoria="Papeles",
            proveedor="Proveedor A",
            cantidad=Q3("500"),  # 500 resmas
            unidad="Resmas",
            stock_minimo=Q3("50"),
            costo_unitario=Q2("15"),
            ultima_actualizacion=date.today(),
            largo_cm=Q3("29.7"),
            ancho_cm=Q3("21"),
            gramaje_grs=Q3("80")
        )
        db.add(papel_a4)
        db.flush()

        papel_opalina = models.ArticuloStock(
            nombre="Opalina blanca 300 gr",
            categoria="Papeles",
            proveedor="Proveedor B",
            cantidad=Q3("200"),
            unidad="Pliegos",
            stock_minimo=Q3("20"),
            costo_unitario=Q2("25"),
            ultima_actualizacion=date.today(),
            largo_cm=Q3("70"),
            ancho_cm=Q3("100"),
            gramaje_grs=Q3("300")
        )
        db.add(papel_opalina)
        db.flush()

        tinta_negra = models.ArticuloStock(
            nombre="Tinta negra 1kg",
            categoria="Tintas",
            proveedor="Proveedor Tintes",
            cantidad=Q3("5"),
            unidad="Kg",
            stock_minimo=Q3("1"),
            costo_unitario=Q2("180"),
            ultima_actualizacion=date.today()
        )
        db.add(tinta_negra)
        db.flush()

        print("📋 Creando presupuestos...")
        # Presupuesto 1: 2 ítems para cliente1 (serán 2 trabajos del mismo cliente)
        presupuesto1 = models.Presupuesto(
            cliente_id=cliente1.id,
            numero_secuencia="0001-000001",
            estado="Borrador",
            fecha_creacion=date.today()
        )
        db.add(presupuesto1)
        db.flush()

        # Ítem 1: Tarjetas de presentación
        item1_1 = models.ItemPresupuesto(
            presupuesto_id=presupuesto1.id,
            orden=1,
            descripcion="Tarjetas de presentación",
            cantidad=1000,
            precio_unitario=Q2("0.15"),
            material="Opalina blanca 300 gr",
            papel_id=papel_opalina.id,
            cantidad_pliegos=Q3("10"),
            costo_materiales=Q2("50")
        )
        db.add(item1_1)
        db.flush()

        # Ítem 2: Membretería (factor de mismo presupuesto)
        item1_2 = models.ItemPresupuesto(
            presupuesto_id=presupuesto1.id,
            orden=2,
            descripcion="Membretería",
            cantidad=500,
            precio_unitario=Q2("0.20"),
            material="Papel A4 80 gr blanco",
            papel_id=papel_a4.id,
            cantidad_pliegos=Q3("25"),
            costo_materiales=Q2("30")
        )
        db.add(item1_2)
        db.flush()

        # Presupuesto 2: 1 ítem para cliente2
        presupuesto2 = models.Presupuesto(
            cliente_id=cliente2.id,
            numero_secuencia="0001-000002",
            estado="Borrador",
            fecha_creacion=date.today()
        )
        db.add(presupuesto2)
        db.flush()

        # Ítem único: Folletos
        item2_1 = models.ItemPresupuesto(
            presupuesto_id=presupuesto2.id,
            orden=1,
            descripcion="Folletos trípticos a color",
            cantidad=2000,
            precio_unitario=Q2("0.50"),
            material="Papel A4 80 gr blanco",
            papel_id=papel_a4.id,
            cantidad_pliegos=Q3("50"),
            costo_materiales=Q2("120")
        )
        db.add(item2_1)
        db.flush()

        print("🔄 Convirtiendo presupuestos a trabajos...")
        # Convertir presupuesto 1 a trabajos
        _convertir_presupuesto(db, presupuesto1, cliente1)

        # Convertir presupuesto 2 a trabajos
        _convertir_presupuesto(db, presupuesto2, cliente2)

        db.commit()

        # Ahora que tenemos los trabajos, obtenemos los IDs para asociar gastos/cheques
        trabajos = db.query(models.Trabajo).all()
        trabajo1 = trabajos[0]
        trabajo2 = trabajos[1]
        trabajo3 = trabajos[2]

        print("💰 Creando gastos...")
        # Gastos asociados a trabajos
        gasto1 = models.Gasto(
            trabajo_id=trabajo1.id,
            categoria="Materiales",
            concepto="Compra de opalina",
            monto=Q2("180"),
            fecha=date.today() - timedelta(days=3),
            metodo_pago="Transferencia",
            comprobante="Factura Proveedor A #5483",
            responsable="Facundo"
        )
        db.add(gasto1)

        gasto2 = models.Gasto(
            trabajo_id=trabajo2.id,
            categoria="Servicios",
            concepto="Servicio de encuadernación",
            monto=Q2("85"),
            fecha=date.today() - timedelta(days=2),
            metodo_pago="Efectivo",
            comprobante="Sin comprobante",
            responsable="Taller"
        )
        db.add(gasto2)

        # Gasto general sin asociación a trabajo
        gasto3 = models.Gasto(
            categoria="Servicios",
            concepto="Alquiler de máquina por día",
            monto=Q2("250"),
            fecha=date.today() - timedelta(days=1),
            metodo_pago="Efectivo",
            comprobante="Recibo",
            responsable="General"
        )
        db.add(gasto3)

        print("💳 Creando cheques...")
        # Cheque recibido de cliente1 (asociado a trabajo1)
        cheque1 = models.Cheque(
            cliente_id=cliente1.id,
            trabajo_id=trabajo1.id,
            clasificacion="Recibido",
            banco="Banco Nación",
            numero="0012345",
            monto=Q2("150"),
            fecha_emision=date.today() - timedelta(days=5),
            fecha_cobro=date.today() + timedelta(days=10),
            estado="En Cartera"
        )
        db.add(cheque1)

        # Cheque recibido de cliente2
        cheque2 = models.Cheque(
            cliente_id=cliente2.id,
            clasificacion="Recibido",
            banco="Banco Santander",
            numero="0098765",
            monto=Q2("1000"),
            fecha_emision=date.today() - timedelta(days=2),
            fecha_cobro=date.today() + timedelta(days=15),
            estado="Depositado"
        )
        db.add(cheque2)

        print("📊 Creando movimientos (pagos)...")
        # Movimiento de pago parcial para trabajo1
        movimiento1 = models.Movimiento(
            cliente_id=cliente1.id,
            trabajo_id=trabajo1.id,
            fecha=datetime.now(),
            monto=Q2("75"),
            tipo="Pago",
            metodo="Efectivo",
            descripcion="Seña / pago parcial"
        )
        db.add(movimiento1)

        # Movimiento de pago para trabajo3
        movimiento2 = models.Movimiento(
            cliente_id=cliente2.id,
            trabajo_id=trabajo3.id,
            fecha=datetime.now() - timedelta(hours=2),
            monto=Q2("500"),
            tipo="Pago",
            metodo="Transferencia",
            descripcion="Pago inicial"
        )
        db.add(movimiento2)

        db.commit()

        print("\n✅ Base de datos poblada exitosamente!")
        print(f"   • 2 clientes creados")
        print(f"   • 3 trabajos en estado 'Aprobado' (Kanban)")
        print(f"     - 2 del cliente '{cliente1.nombre_completo}' (mismo presupuesto)")
        print(f"     - 1 del cliente '{cliente2.nombre_completo}'")
        print(f"   • 3 artículos de stock")
        print(f"   • 3 gastos")
        print(f"   • 2 cheques")
        print(f"   • 2 movimientos (pagos)")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def _convertir_presupuesto(db: Session, presupuesto: models.Presupuesto, cliente: models.Cliente):
    """Simula la conversión de presupuesto a trabajos (sin pasar por el router)."""
    for item in presupuesto.items:
        nuevo_trabajo = models.Trabajo(
            cliente_id=presupuesto.cliente_id,
            descripcion_producto=item.descripcion,
            cantidad=item.cantidad,
            precio_venta=Q2(item.cantidad * item.precio_unitario),
            costo_total_materiales=item.costo_materiales or Q2("0"),
            notas_iniciales=f"Viene del presupuesto {presupuesto.numero_secuencia or 's/n'}",
            fecha_creacion=date.today(),
            estado="Aprobado",
            papel_id=item.papel_id,
            cantidad_pliegos=item.cantidad_pliegos,
            papel_tipo=item.material,
        )
        db.add(nuevo_trabajo)
        db.flush()
        item.trabajo_id = nuevo_trabajo.id

    presupuesto.convertido_a_trabajo = True
    presupuesto.estado = "Aprobado"


if __name__ == "__main__":
    crear_datos_ejemplo()
