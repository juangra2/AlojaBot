# Pricing dinámico y descuentos (AlojaBot)

Este documento describe la lógica de **pricing dinámico** aplicada por AlojaBot en el proceso de reserva y modificación de reservas.  
El objetivo es **incentivar la ocupación de última hora** mediante descuentos automáticos y transparentes, sin romper las reglas de negocio del sistema.

## Objetivo del pricing dinámico
- Aumentar la conversión cuando una fecha de entrada está cerca (última hora).
- Ajustar el precio de forma **automática** siguiendo reglas deterministas (no “inventadas” por el LLM).
- Mantener **transparencia**: el usuario ve el precio base, el descuento y el total antes de confirmar.

## Conceptos clave
- **precio_noche_base**: precio original por noche del alojamiento (desde alojamientos.xlsx).
- **descuento_pct**: porcentaje de descuento dinámico (por ejemplo 0.10 = 10%).
- **precio_noche_final**: precio por noche tras aplicar descuento.
- **precio_total**: total estimado en función de noches y precio_noche_final.

## Regla general de cálculo
El descuento se calcula principalmente según la cercanía de la fecha de check-in respecto a “hoy”:

- Cuanto **más cercano** el check-in, **mayor** descuento (dentro de un umbral de días).
- Si el check-in está “lejano”, el descuento tiende a 0%.

> Nota: el descuento se calcula con una función determinista, típicamente:
> - `dynamic_discount_pct(check_in, today, ...)`
> - `apply_discount(precio_base, pct)`

## Cuándo se aplica
### 1) Reserva nueva
Antes de confirmar la reserva:
- El bot calcula **precio_noche_base** (del alojamiento).
- Calcula **descuento_pct** según check-in.
- Muestra:
  - Precio base
  - Descuento
  - Precio final por noche
  - Total estimado

Tras confirmar:
- Se persisten en reservas.xlsx:
  - precio_noche_base
  - descuento_pct
  - precio_noche_final
  - precio_total

### 2) Modificación de reserva
Si se cambian fechas (especialmente el check-in), el descuento puede variar:
- Se recalcula **descuento_pct** con el nuevo check-in.
- Se actualizan los campos de precio y el total final.
- El usuario ve el nuevo total antes de confirmar.

## Transparencia y comunicación al usuario
AlojaBot muestra el descuento con un formato “explicable”, por ejemplo:
- “💸 Descuento dinámico: 10% (de 120 → 108 €/noche).”
- “💶 Total estimado: 216 € (a 108 €/noche).”

Esto evita confusión y mejora la confianza del usuario.

## Persistencia en Excel (reservas.xlsx)
Cuando el sistema guarda una reserva (creación o modificación), se mantienen columnas clave:
- `precio_noche_base`
- `descuento_pct`
- `precio_noche_final`
- `precio_total`

Si el Excel es antiguo y no tiene estas columnas, el backend debe poder:
- Crear columnas faltantes automáticamente al cargar/guardar.

## Ejemplo numérico
- Precio base: 100 €/noche
- Check-in dentro de ventana de última hora → descuento 15%
- Precio final: 85 €/noche
- 2 noches → total = 170 €

## Limitaciones y decisiones de diseño
- El LLM **no decide** el descuento.
- El LLM puede explicar el descuento, pero **no modificar** la regla.
- El cálculo es determinista y auditable (ideal para memoria académica).

## Preguntas típicas que debe poder responder el bot
- “¿Tenéis descuentos?”
- “¿Por qué me sale más barato si reservo para mañana?”
- “¿Qué descuento se aplica si reservo dentro de X días?”
- “¿Se mantiene el descuento si cambio las fechas?”

## Mensaje sugerido para atención al usuario
“Aplicamos descuentos automáticos en reservas con check-in cercano para incentivar disponibilidad de última hora.  
El precio final se muestra antes de confirmar, indicando el descuento aplicado y el total estimado.”