# Seguridad y privacidad

## Alcance

Esta distribución separa el código compartible del alojamiento privado. Incluye únicamente ejemplos genéricos, pruebas sintéticas y el backend/interfaz local. No necesita credenciales, no incluye datos de cartera, historial Git original ni configuración de Sites.

El servidor escucha solo en `127.0.0.1`, verifica el encabezado Host y rechaza orígenes extranjeros. Los archivos servidos pertenecen a una lista cerrada: no expone carpetas, fuentes Python ni archivos de configuración. La consulta valida símbolos y combinaciones de intervalo/rango; su destino HTTPS está fijo y no sigue redirecciones. No desactiva la verificación de certificados. La interfaz usa texto del DOM para nombres y errores del proveedor, no interpreta ese contenido como HTML.

El servidor se basa en la biblioteca estándar de Python. [Su documentación oficial](https://docs.python.org/3/library/http.server.html) advierte que `http.server` no es apropiado para producción en Internet. No lo expongas con túneles, redirecciones de puertos ni interfaces de red públicas. Los controles locales son defensa adicional, no una garantía contra software malicioso que ya se ejecute en la computadora.

## Datos tratados

- Las preferencias/tickers se guardan en el almacenamiento local del navegador. Puedes eliminarlos desde los datos de ese sitio local.
- Python conserva una caché limitada en memoria; termina al cerrar el proceso. No guarda precios ni logs de acceso en disco.
- Los símbolos, intervalo y rango se envían a Yahoo Finance. El proveedor puede registrar las consultas y su origen según sus políticas.
- No hay telemetría propia, cookies de autenticación, conexión a cuentas financieras ni ejecución de operaciones.

## Revisión pública

`python -B scripts/check_public.py` detecta patrones de credenciales, correos, rutas personales, URL de publicación y tipos de archivo privados. Informa solo el nombre del archivo y la categoría, nunca el posible valor secreto. Omite `.git` y carpetas generadas: no analiza historial ni acredita que todas las credenciales posibles sean detectables.

La entrega se revisó por lista de archivos y con este escáner, pero ninguna revisión garantiza seguridad absoluta. Mantén Python y el navegador actualizados; revisa cambios y dependencias futuras. La ejecución directa no instala librerías de terceros.

Crea un repositorio **nuevo** con esta carpeta: no copies `.git`, configuraciones de publicación ni archivos privados del proyecto original. Si detectas un secreto ya publicado, revócalo; borrarlo del archivo más reciente no lo elimina del historial. No pegues credenciales en issues públicos.
