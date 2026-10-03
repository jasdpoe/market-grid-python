# Revisión de la distribución pública

Fecha: 2026-10-03. Se revisó el contenido de esta distribución; no es una certificación de seguridad absoluta.

## Separación

- Núcleo Python independiente, servidor local e interfaz HTML/JavaScript sin compilación ni dependencias de ejecución externas.
- Ejemplos genéricos y pruebas sintéticas. Sin cartera, precios persistidos, credenciales ni direcciones/identificadores del despliegue existente.
- Sin historial Git heredado ni configuración de alojamiento en el paquete. Las notas de integración privada quedan fuera.
- Servidor limitado a loopback, origen/Host validados, lista cerrada de archivos públicos y destino de mercado fijo con TLS verificado.

## Comprobaciones realizadas

- Pruebas Python: indicadores, filtrado de datos incompletos, rangos separados en caché, validación, API, archivos públicos, rechazo de orígenes ajenos y manejo de errores sin trazas.
- Pruebas JavaScript: historial corto intacto, agrupación sin truncar el período y agregación correcta de OHLC/volumen con indicadores originales.
- Consulta real de AAPL diario: seis meses devolvió 126 velas y un año 251. La diferencia de inicio se verificó además en la vista ampliada.
- Comprobación en navegador: carga de 17 activos con cuatro columnas, controles sincronizados entre vistas, fallback de rango intradía, Escape para regresar y ausencia de errores en consola durante esas pruebas.
- Revisión de archivos públicos mediante el escáner incluido. El ZIP se construye solo con archivos permitidos del paquete.

El período de actualización automática se configura en 300 000 ms; la comprobación de interfaz no constituye una prueba prolongada de temporizadores con el navegador en segundo plano. Los datos reales, sus recuentos y la disponibilidad del proveedor cambian con el tiempo.

## Límites

El escáner no analiza historial Git ni detecta todos los secretos posibles. La ejecución directa no incluye dependencias de terceros que auditar, pero Python, el navegador y el proveedor de datos tienen sus propios riesgos y actualizaciones. No se han realizado pruebas de penetración ni validación en todos los sistemas operativos/versiones admitidos. No se incluye una licencia elegida por el propietario.
