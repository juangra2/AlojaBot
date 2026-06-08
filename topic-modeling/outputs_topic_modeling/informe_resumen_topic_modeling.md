# Informe de topic modeling sobre respuestas abiertas

## 1. Contexto

Este análisis se ha realizado sobre las respuestas abiertas del formulario de evaluación de usuarios del TFM. El objetivo es identificar temas recurrentes relacionados con la experiencia de uso de la web, el asistente conversacional, el flujo de reserva, el diseño, la rapidez, la disponibilidad, los precios y otras funcionalidades del sistema.

## 2. Configuración del análisis

- Columna analizada: `Opinión final
Respuesta larga: “Cuéntanos tu opinión final sobre la experiencia. ¿Qué te ha gustado más y qué mejorarías?”  `
- Método de topic modeling usado: **BERTopic**
- Lematización con spaCy: **sí**

## 3. Análisis descriptivo

- numero_respuestas: 25
- longitud_media_palabras: 37.64
- longitud_mediana_palabras: 36.0
- longitud_minima_palabras: 31
- longitud_maxima_palabras: 49
- numero_respuestas_vacias_tras_limpieza: 0

## 4. Temas detectados

### Tema 0: Tema 0: reserva

- Número de respuestas: 8
- Porcentaje: 32.0%
- Palabras clave: reserva, asistente, información, útil, mejoraría, flujo, resultado, especialmente, alojamiento, flujo reserva
- Interpretación automática: Tema relacionado con el flujo de reserva, confirmación o gestión de reservas. Tema relacionado con la utilidad, claridad o precisión de las respuestas del asistente conversacional.
- Ejemplos representativos:
  - La experiencia ha sido positiva. El flujo de reserva se entiende bien y el asistente responde rápido. Me ha resultado útil que indique qué datos faltan. Mejoraría un poco el diseño del calendario para que se diferencie todavía más qué días están ocupados y cuáles libres.
  - Me ha resultado sencillo reservar. El asistente guía bastante bien y evita tener que buscar manualmente disponibilidad. Me ha gustado que pregunte por confirmación antes de guardar la reserva. Mejoraría la parte de meteorología, mostrando quizá una tabla por días.
  - El flujo de reserva es claro y rápido. El asistente entiende bien la intención y va directo al punto. Me parece especialmente útil para usuarios que quieren consultar disponibilidad sin llamar o escribir varios mensajes. Mejoraría algunos textos para que sean más cortos.

### Tema 1: Tema 1: añadiría

- Número de respuestas: 7
- Porcentaje: 28.0%
- Palabras clave: añadiría, respuestas, chat, mejora, útil, gustado, catálogo, respuestas asistente, inicial, asistente
- Interpretación automática: Tema relacionado con la utilidad, claridad o precisión de las respuestas del asistente conversacional.
- Ejemplos representativos:
  - Me ha gustado la combinación de catálogo visual y chat. Es más cómodo que escribir todo desde cero. Las respuestas del asistente son útiles y no se sienten genéricas. Como mejora, estaría bien incluir más información sobre políticas de cancelación antes de reservar.
  - La idea me parece útil, aunque en algún momento no sabía exactamente qué formato de fecha usar. El sistema acaba ayudando, pero pondría ejemplos más visibles. Las respuestas son buenas y el diseño está cuidado.
  - La herramienta es útil, pero al principio me costó entender que podía escribir de forma natural. El asistente responde bien, aunque haría la interfaz un poco más explicativa. Añadiría una guía breve de ejemplos de uso.

### Tema 2: Tema 2: web

- Número de respuestas: 6
- Porcentaje: 24.0%
- Palabras clave: web, bot, entiende, datos, flujo, fácil, clara, inicio, pedir, principio
- Interpretación automática: Tema relacionado con el flujo de reserva, confirmación o gestión de reservas. Tema relacionado con la utilidad, claridad o precisión de las respuestas del asistente conversacional.
- Ejemplos representativos:
  - La web me ha parecido muy clara y fácil de usar. Me ha gustado especialmente que se vean los alojamientos desde el inicio y que el bot vaya pidiendo solo los datos necesarios para completar la reserva. Como mejora, añadiría un resumen visual final más destacado antes de confirmar.
  - La web tiene un diseño agradable y profesional. El flujo general se entiende, aunque al principio no estaba seguro de si tenía que escribir todos los datos juntos o poco a poco. El bot lo aclara bien, pero quizá pondría un ejemplo visible desde el inicio.
  - La web funciona bien, pero el flujo de reserva podría explicar desde el principio todos los datos que se van a pedir. Me gustó que el asistente no confirme nada sin preguntar antes. La interfaz es bastante limpia.

### Tema 3: Tema 3: bot

- Número de respuestas: 3
- Porcentaje: 12.0%
- Palabras clave: bot, gustado bot, calendario, reserva, mejoraría, gustado, añadiría, ahorrar, confirmación seguridad, bot guía
- Interpretación automática: Tema relacionado con calendario, fechas y disponibilidad del alojamiento. Tema relacionado con el flujo de reserva, confirmación o gestión de reservas. Tema relacionado con la utilidad, claridad o precisión de las respuestas del asistente conversacional. Tema relacionado con confianza, seguridad o transparencia del proceso.
- Ejemplos representativos:
  - Muy buena experiencia. Me ha gustado que el bot pueda responder dudas del alojamiento y también hacer la reserva. Parece una herramienta real para ahorrar tiempo al propietario. Añadiría un botón para copiar el resumen de la reserva.
  - El proceso es muy intuitivo. Me ha gustado que el bot pida los datos que faltan sin obligar a repetir todo. La confirmación final da seguridad. Mejoraría el contraste de algunos elementos del calendario.
  - El sistema me parece muy cómodo para gestionar una reserva sin intervención manual. El bot guía bien y la web responde rápido. Mejoraría la explicación del calendario y añadiría una leyenda más visible.

### Tema -1: Tema -1: respuestas no agrupadas

- Número de respuestas: 1
- Porcentaje: 4.0%
- Palabras clave: outliers / respuestas no agrupadas
- Interpretación automática: Tema relacionado con la utilidad, claridad o precisión de las respuestas del asistente conversacional.
- Ejemplos representativos:
  - Me ha gustado mucho la parte visual de los apartamentos. Ayuda a decidir antes de hablar con el bot. Las respuestas son útiles y el sistema parece rápido. Como mejora, añadiría filtros visibles por número de personas o precio.

## 5. Palabras más frecuentes

| palabra        |   frecuencia |
|:---------------|-------------:|
| reserva        |           17 |
| gustar         |           12 |
| asistente      |           12 |
| útil           |           11 |
| web            |            8 |
| bot            |            8 |
| mejora         |            8 |
| flujo          |            8 |
| añadir         |            8 |
| dato           |            7 |
| responder      |            7 |
| rápido         |            7 |
| respuesta      |            7 |
| pedir          |            6 |
| experiencia    |            6 |
| entender       |            6 |
| disponibilidad |            6 |
| visual         |            5 |
| diseño         |            5 |
| escribir       |            5 |
| información    |            5 |
| confirmación   |            5 |
| sistema        |            5 |
| especialmente  |            4 |
| resumen        |            4 |
| confirmar      |            4 |
| mejorar        |            4 |
| calendario     |            4 |
| ejemplo        |            4 |
| visible        |            4 |

## 6. Bigramas y trigramas frecuentes

| ngrama                     |   frecuencia |
|:---------------------------|-------------:|
| flujo reserva              |            6 |
| asistente responder        |            4 |
| responder rápido           |            4 |
| consultar disponibilidad   |            3 |
| mejora incluir             |            3 |
| pedir dato                 |            3 |
| resolver duda              |            3 |
| bot pedir                  |            2 |
| funcionar flujo reserva    |            2 |
| asistente responder rápido |            2 |
| gustar especialmente       |            2 |
| flujo reserva entender     |            2 |
| ejemplo visible            |            2 |
| bot pedir dato             |            2 |
| gustar bot                 |            2 |
| dato faltar                |            2 |
| completar reserva          |            2 |
| funcionar flujo            |            2 |
| incluir información        |            2 |
| información reserva        |            2 |
| mejora añadir              |            2 |
| mejora incluir información |            2 |
| pedir confirmación         |            2 |
| reserva entender           |            2 |
| respuesta asistente        |            2 |
| respuesta útil             |            2 |
| resultar útil              |            2 |
| resumen visual             |            2 |
| web responder              |            2 |
| web responder rápido       |            2 |

## 7. Mejoras priorizadas

### Asistente conversacional

- Frecuencia de menciones: 25
- Porcentaje de respuestas: 100.0%
- Menciones con fricción o mejora: 24
- Puntuación de prioridad: 49.0
- Propuesta accionable: Mejorar la cobertura de respuestas del asistente, añadir ejemplos de preguntas y reforzar mensajes cuando no tenga suficiente información.

### Flujo de reserva

- Frecuencia de menciones: 18
- Porcentaje de respuestas: 72.0%
- Menciones con fricción o mejora: 17
- Puntuación de prioridad: 35.0
- Propuesta accionable: Simplificar el flujo de reserva, añadir mensajes de confirmación más claros y destacar las opciones de modificación o cancelación.

### Diseño e interfaz

- Frecuencia de menciones: 15
- Porcentaje de respuestas: 60.0%
- Menciones con fricción o mejora: 15
- Puntuación de prioridad: 30.0
- Propuesta accionable: Pulir jerarquía visual, botones principales, legibilidad y adaptación móvil para reducir fricción de navegación.

### Confianza y transparencia

- Frecuencia de menciones: 13
- Porcentaje de respuestas: 52.0%
- Menciones con fricción o mejora: 12
- Puntuación de prioridad: 25.0
- Propuesta accionable: Añadir señales de confianza: confirmaciones claras, resumen final de reserva, datos del alojamiento y mensajes de seguridad.

### Calendario y disponibilidad

- Frecuencia de menciones: 11
- Porcentaje de respuestas: 44.0%
- Menciones con fricción o mejora: 11
- Puntuación de prioridad: 22.0
- Propuesta accionable: Reforzar la claridad visual del calendario, mostrar estados de disponibilidad con más evidencia y explicar mejor cómo se seleccionan fechas.

### Rapidez y rendimiento

- Frecuencia de menciones: 9
- Porcentaje de respuestas: 36.0%
- Menciones con fricción o mejora: 9
- Puntuación de prioridad: 18.0
- Propuesta accionable: Optimizar tiempos de carga, respuestas del bot y transiciones entre pasos clave.

### Precios y descuentos

- Frecuencia de menciones: 3
- Porcentaje de respuestas: 12.0%
- Menciones con fricción o mejora: 3
- Puntuación de prioridad: 6.0
- Propuesta accionable: Explicar mejor el cálculo del precio final, descuentos aplicados y condiciones del pricing dinámico.

### Meteorología

- Frecuencia de menciones: 3
- Porcentaje de respuestas: 12.0%
- Menciones con fricción o mejora: 3
- Puntuación de prioridad: 6.0
- Propuesta accionable: Integrar la meteorología de forma contextual, por ejemplo vinculada a la estancia o a recomendaciones para Toledo/Cobisa.

### Panel de administración

- Frecuencia de menciones: 1
- Porcentaje de respuestas: 4.0%
- Menciones con fricción o mejora: 1
- Puntuación de prioridad: 2.0
- Propuesta accionable: Mejorar la lectura de métricas, filtros de reservas y visibilidad de acciones administrativas.

## 8. Cómo interpretar los resultados en la memoria

Los temas detectados deben interpretarse como agrupaciones exploratorias de opiniones de usuario. Para la memoria del TFM, se recomienda combinar la tabla de temas con ejemplos textuales representativos y con la tabla de mejoras priorizadas. La interpretación automática puede utilizarse como punto de partida, pero conviene revisarla manualmente para asegurar que cada tema queda descrito de forma fiel al contenido de las respuestas.
