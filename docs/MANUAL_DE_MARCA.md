# Manual de Marca y Sistema de Diseño (MB) · SynchroData
**Inspiración Apple Design · Colores Sólidos y Mate · Máximo Aprovechamiento Espacial**
*Versión 4.0 · HackMTY 2026*

---

## 1. Filosofía de Identidad y Diseño

SynchroData es la plataforma de compra inteligente y transparente en Monterrey, diseñada para asistir a los consumidores evaluando señales de riesgo, comparando ofertas reales y trazando rutas de recogida eficientes.

### Los Tres Pilares de Diseño (Estilo Apple):
1. **Claridad & Tipografía Robusta**: La información crítica (riesgo, precio, inventario, ruta) tiene jerarquía incuestionable. Tipografía SF Pro con espaciado óptico calibrado.
2. **Solidez y Acabado Mate**: Adiós a los degradados plásticos, reflejos estridentes o brillos innecesarios. Se utilizan superficies sólidas, tonos mate con textura de aluminio anodizado y contrastes aprobados por accesibilidad WCAG AAA / AA.
3. **Aprovechamiento Espacial Inteligente**: Distribución balanceada en dos paneles (Inteligencia de Producto y Mapa Interactivo) que elimina espacios muertos, optimiza el flujo en laptops y dispositivos móviles, y mantiene siempre a la vista las herramientas clave.

---

## 2. Paleta de Colores Oficial (Sólidos y Mate)

Todos los tonos han sido formulados para proyectar precisión tecnológica, sobriedad y confianza institucional.

### 2.1 Colores de Lienzo y Superficies (Canvas)

| Token | Nombre | HEX | RGB | Uso / Propósito |
| :--- | :--- | :--- | :--- | :--- |
| `--apple-bg` | **Lienzo Mate** | `#F5F5F7` | `rgb(245, 245, 247)` | Fondo general del sistema (Apple Gray 6). No fatiga la vista. |
| `--apple-card` | **Tarjeta Sólida** | `#FFFFFF` | `rgb(255, 255, 255)` | Superficie de paneles principales, tarjetas de producto y hoja de mapa. |
| `--apple-surface-muted`| **Pizarra Mate Neutro** | `#F1F5F9` | `rgb(241, 245, 249)` | Fondos de botones secundarios, interruptores inactivos y campos. |
| `--apple-surface-tint` | **Contenedor Suave** | `#F8FAFC` | `rgb(248, 250, 252)` | Listas vacías, inputs en reposo e imágenes de producto. |

### 2.2 Textos y Jerarquía Tipográfica

| Token | Nombre | HEX | Ratio Contraste | Uso |
| :--- | :--- | :--- | :--- | :--- |
| `--apple-text-primary` | **Apple Off-Black** | `#1D1D1F` | **14.8:1 (AAA)** | Títulos principales (H1, H2), precios, nombres de tiendas y datos clave. |
| `--apple-text-secondary`| **Gris Pizarra Mate** | `#64748B` | **4.9:1 (AA)** | Subtítulos, descripciones secundarias, timestamps y etiquetas de origen. |
| `--apple-text-tertiary` | **Gris Auxiliar** | `#86868B` | **3.8:1** | Leyendas pequeñas, avisos legales y contadores de navegación. |

### 2.3 Acento Principal (SynchroData Pine / Apple Forest)

Representa ecología, confianza y verificación en Monterrey. Acabado verde bosque mate profundo.

| Token | Nombre | HEX | RGB | Aplicación |
| :--- | :--- | :--- | :--- | :--- |
| `--apple-green` | **Verde Bosque Sólido** | `#007A53` | `rgb(0, 122, 83)` | Botón primario de análisis, enlaces activos, ruta en mapa y pines. |
| `--apple-green-hover` | **Bosque Profundo (Hover)** | `#006646` | `rgb(0, 102, 70)` | Estado hover en botones primarios. |
| `--apple-green-bg` | **Menta Mate Suave** | `#F0FDF4` | `rgb(240, 253, 244)` | Fondo de tarjetas verificadas, banderas verdes y total de compras. |
| `--apple-green-border`| **Borde Menta Sólido** | `#BBF7D0` | `rgb(187, 247, 208)` | Delimitador de tarjetas de confirmación y badges de estado. |
| `--apple-green-text` | **Texto Verde Follaje** | `#166534` | `rgb(22, 101, 52)` | Tipografía para banderas positivas y etiquetas de éxito. |

### 2.4 Colores Semánticos de Estado (Sólidos y Mate)

| Estado | Token Color | HEX | Fondo Sólido Mate | Borde | Mensaje / Rol |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Alerta / Riesgo** | `--apple-red` | `#DC2626` | `#FEF2F2` | `#FECACA` | Banderas rojas, fallas de validación y tiendas de alto riesgo. |
| **Advertencia** | `--apple-amber` | `#D97706` | `#FFFBEB` | `#FDE68A` | Banderas pendientes, modo demo y discrepancia de inventario. |
| **Tránsito / Sistema** | `--apple-blue` | `#0071E3` | `#EFF6FF` | `#BFDBFE` | Punto de salida (Macroplaza / Mi ubicación) y enlaces externos. |

---

## 3. Sistema Tipográfico (Apple Typography Scale)

Basado en la familia nativa del sistema Apple (`SF Pro Display` para títulos y `SF Pro Text` para controles e interfaces).

```css
font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", Roboto, sans-serif;
```

| Nivel | Tamaño | Peso | Tracking | Interlineado | Uso |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Hero Title** | `34px` | Bold (750) | `-0.035em` | `1.15` | "Compra con más contexto." |
| **H1 / Sección** | `26px` | Bold (700) | `-0.030em` | `1.20` | Encabezados de Marca y Secciones Primarias. |
| **H2 / Tarjeta** | `20px` | Bold (700) | `-0.020em` | `1.25` | "Resultado del análisis", "Compara tus opciones". |
| **H3 / Título Item**| `16px` | Semibold (650) | `-0.015em` | `1.30` | Títulos en ofertas de tiendas y panel de ruta. |
| **Cuerpo (Body)** | `14px` | Regular (400) | `-0.010em` | `1.50` | Párrafos generales y explicaciones del análisis. |
| **Control / Botón**| `13.5px`| Semibold (650) | `0.000em` | `1.00` | Botones de acción, interruptores y menús desplegables. |
| **Leyenda (Small)** | `11px` | Medium (500) | `+0.010em` | `1.40` | Timestamps, notas de fuente, pie de panel y badges. |

---

## 4. Tokens de Forma, Elevación y Espaciado ("Aprovechamiento Espacial")

### 4.1 Radios de Esquina (Apple Squircle Curves)
- **Chips y Badges Píldora (`--radius-pill`)**: `9999px` — Usado en el conmutador de idioma `[ ES | EN ]`, selector de modo `[ Real | Demo ]` y contadores.
- **Tarjetas Principales (`--radius-xl`)**: `20px` — Contenedor de búsqueda, panel de resultados, mapa y hoja inferior de ruta.
- **Tarjetas Secundarias (`--radius-lg`)**: `16px` — Tarjetas de oferta de tiendas y caja de riesgo.
- **Elementos de Interacción (`--radius-md`)**: `12px` — Inputs de búsqueda, banderas de verificación y botones de acción.
- **Controles Pequeños (`--radius-sm`)**: `8px` — Dropdowns de sucursales e iconos auxiliares.

### 4.2 Elevaciones y Sombras Mate (Difusión Suave)
- **Sombra Suave (`--apple-shadow-sm`)**: `0 1px 3px rgba(0,0,0,0.04)`
- **Sombra Media (`--apple-shadow-md`)**: `0 4px 16px rgba(0,0,0,0.05)` (Tarjetas principales sin reflejos).
- **Sombra Alta (`--apple-shadow-lg`)**: `0 12px 36px rgba(0,0,0,0.08)` (Hoja flotante de ruta y controles superiores de mapa).

---

## 5. Especificación de Componentes Clave

### 5.1 Conmutador de Idioma Segmentado (`[ ES | EN ]`)
- Ubicado en la barra superior junto al selector de modo y la ubicación de Monterrey.
- Estructurado como un **Apple Segmented Control**:
  - Contenedor con radio píldora (`#E2E8F0`) y borde mate suave (`#D1D5DB`).
  - Pestaña activa resaltada en blanco puro mate (`#FFFFFF`) con micro-sombra táctil.
  - Totalmente accesible mediante `role="radiogroup"` y estados de foco visibles.

### 5.2 Barra de Búsqueda Estilo Apple Spotlight
- Diseño amplio integrado en la cabecera del espacio de trabajo.
- Campo de entrada con icono de enlace tipográfico, fondo tenue mate (`#F8FAFC`), transición suave a blanco puro y halo de foco verde bosque (`0 0 0 3px rgba(0,122,83,0.18)`).
- Botón de análisis con flecha indicadora y compresión al clic (`transform: scale(0.98)`).

### 5.3 Grícula de Banderas de Verificación
- Presentación en 3 columnas homogéneas:
  1. **Bandera Verde**: Señales positivas verificadas (ej. Conexión HTTPS, comercio reconocido).
  2. **Bandera Roja**: Alertas detectadas con evidencia disponible.
  3. **Bandera Pendiente**: Datos aún no disponibles, aclarando que no representan automáticamente riesgo.

### 5.4 Panel de Recorrido de Pickup (Apple Maps Sheet)
- Panel flotante anclado en la parte inferior del mapa con tirador superior (`pill pull handle`).
- Línea de tiempo visual que une el origen con cada parada de tienda mediante marcadores numerados y líneas conectoras continuas.
- Cálculo de distancias en kilómetros y tiempos estimados de trayecto.

---

## 6. Arquitectura de Internacionalización (i18n)

### 6.1 Diagnóstico y Optimización Realizada
1. **Idioma por Defecto Inteligente**:
   - Se estableció **Español (`es`)** como el idioma oficial y predeterminado del proyecto (acorde a la sede HackMTY en Monterrey y las pruebas de usuario).
   - Se mantiene la detección y persistencia en `localStorage`, respetando las elecciones previas sin provocar saltos de diseño (*layout shifts*).
2. **Sincronización del DOM**:
   - Actualización dinámica de `<html lang="es">` / `<html lang="en">` en tiempo de ejecución para garantizar correcta indexación, accesibilidad mediante lectores de pantalla y correctores ortográficos del navegador.
3. **Centralización en Diccionario Fuertemente Tipado**:
   - Toda la interfaz consume `src/lib/i18n.tsx` a través del hook `useLang()`.
   - Se eliminaron cadenas en código duro y condicionales ternarios dispersos en componentes.

---

## 7. Mapeo de Variables CSS

Para implementar este diseño en cualquier módulo o vista adicional, utilice las variables CSS declaradas en `src/app/globals.css`:

```css
/* Ejemplo de uso en nuevos componentes */
.mi-tarjeta-apple {
  background-color: var(--apple-card);
  border: 1px solid var(--apple-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--apple-shadow-md);
  padding: 16px 20px;
  color: var(--apple-text-primary);
}

.mi-boton-mate {
  background-color: var(--apple-green);
  color: #ffffff;
  border-radius: var(--radius-md);
  font-weight: 600;
  padding: 10px 18px;
  transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
}

.mi-boton-mate:hover {
  background-color: var(--apple-green-hover);
}
```
