# AlojaBot

AlojaBot es un asistente conversacional para la consulta y reserva de alojamientos turísticos rurales. El sistema permite consultar información sobre los alojamientos, comprobar disponibilidad, crear reservas, modificarlas, cancelarlas y acceder a un panel de administración con métricas de negocio.

El proyecto combina una interfaz web, un backend en FastAPI, persistencia ligera en ficheros Excel, un módulo RAG sobre documentos Markdown, reglas deterministas para operaciones transaccionales y funcionalidades auxiliares como meteorología, pricing dinámico e internacionalización.

## Tecnologías principales

* Python
* FastAPI
* HTML, CSS y JavaScript
* Chart.js para gráficas del panel de administración
* Ficheros Excel como persistencia ligera
* Corpus Markdown para el módulo RAG

## Estructura general

```text
AlojaBot/
├── api/
│   ├── main.py
│   ├── session_flows.py
│   ├── utils_email.py
│   └── ...
├── data/
│   ├── alojamientos.xlsx
│   ├── calendario.xlsx
│   ├── reservas.xlsx
│   └── corpus/
│       ├── apto_1_mercedes.md
│       ├── apto_2_arcos.md
│       ├── apto_3_bruna.md
│       ├── apto_4_calera.md
│       ├── cobisa_entorno.md
│       └── pricing_dinamico.md
├── static/
├── templates/
├── requirements.txt
└── README.md
```

## Instalación

Clonar el repositorio:

```bash
git clone https://github.com/juangra2/AlojaBot.git
cd AlojaBot
```

Crear y activar un entorno virtual:

```bash
python -m venv .venv
```

En Windows:

```bash
.venv\Scripts\activate
```

En Linux o macOS:

```bash
source .venv/bin/activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

## Configuración

Para utilizar el envío de correos de confirmación, crear un fichero `.env` en la raíz del proyecto con las siguientes variables:

```env
EMAIL_SENDER=tu_correo@gmail.com
EMAIL_PASSWORD=tu_password_o_app_password
```

Los ficheros Excel de datos operativos deben estar en la carpeta `data/`:

```text
data/alojamientos.xlsx
data/calendario.xlsx
data/reservas.xlsx
```

Por motivos de privacidad, los ficheros reales con datos personales no deben subirse al repositorio público.

## Ejecución

Ejecutar el backend con Uvicorn:

```bash
uvicorn api.main:app --reload --port 8000
```

Para acceder a la interfaz web, ejecutar el servidor local:

```bash
cd web
python -m http.server 8080
```

Una vez iniciado el servidor, acceder desde el navegador a:

```text
http://127.0.0.1:8000
```

El panel de administración está disponible en:

```text
http://127.0.0.1:8000/admin
```

## Funcionalidades principales

* Consulta de alojamientos mediante interfaz web y chat.
* Comprobación de disponibilidad.
* Creación de reservas mediante conversación multivuelta.
* Consulta, modificación y cancelación de reservas.
* Verificación de propietario mediante email o DNI/NIE.
* Confirmación de reserva por correo electrónico.
* Módulo RAG para responder preguntas sobre alojamientos y entorno.
* Consulta meteorológica mediante Open-Meteo.
* Pricing dinámico basado en reglas.
* Panel de administración con métricas, filtros, tabla de reservas, exportación CSV y chat administrativo.

## Nota sobre privacidad

El sistema puede trabajar con datos personales asociados a reservas, como nombre, email, teléfono o DNI/NIE. Por ello, los ficheros reales de datos y las credenciales deben mantenerse fuera del repositorio mediante `.gitignore`.

## Autor

Juan Grau Reig
Trabajo Fin de Máster - Máster Universitario en Ciencia de Datos
