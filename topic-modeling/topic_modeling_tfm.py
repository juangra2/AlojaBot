# -*- coding: utf-8 -*-
"""
Topic modeling sobre respuestas abiertas de un formulario de evaluación de usuario.

Proyecto:
TFM en Ciencia de Datos sobre un asistente conversacional para la gestión de alojamientos
turísticos reales en Cobisa/Toledo.

Objetivo:
Analizar respuestas abiertas de Google Forms para identificar temas recurrentes,
aspectos positivos, fricciones y mejoras accionables para la memoria del TFM.

Uso básico:
python topic_modeling_tfm.py --archivo datos_formulario.xlsx

Uso indicando columna abierta:
python topic_modeling_tfm.py --archivo datos_formulario.csv --columna "Cuéntanos tu opinión final sobre la experiencia. ¿Qué te ha gustado más y qué mejorarías?"

Uso forzando NMF:
python topic_modeling_tfm.py --archivo datos_formulario.xlsx --metodo nmf --n_topics 5
"""

import os
import re
import argparse
import warnings
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.decomposition import NMF


# =============================================================================
# CONFIGURACIÓN GENERAL
# =============================================================================

OUTPUT_DIR = "outputs_topic_modeling"

# Palabras que queremos conservar porque son importantes para el TFM.
PALABRAS_RELEVANTES = {
    "reserva", "reservas", "reservar",
    "calendario", "diseño", "rapidez", "rápido", "fluidez",
    "precio", "precios", "descuento", "descuentos", "pricing",
    "bot", "asistente", "alojamiento", "alojamientos",
    "disponibilidad", "web", "panel", "admin",
    "meteorología", "tiempo", "confianza", "usuario", "usuarios",
    "modificar", "cancelar", "consulta", "consultar"
}

# Stopwords básicas en español por si no está disponible spaCy.
STOPWORDS_ES_FALLBACK = {
    "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como", "con",
    "contra", "cual", "cuando", "de", "del", "desde", "donde", "durante",
    "e", "el", "ella", "ellas", "ellos", "en", "entre", "era", "erais",
    "eran", "eras", "eres", "es", "esa", "esas", "ese", "eso", "esos",
    "esta", "estaba", "estaban", "estado", "estáis", "estamos", "están",
    "estar", "estas", "este", "esto", "estos", "estoy", "fue", "fueron",
    "fui", "fuimos", "ha", "había", "habían", "haber", "hace", "hacen",
    "hacer", "hacia", "han", "has", "hasta", "hay", "he", "hemos", "hube",
    "la", "las", "le", "les", "lo", "los", "más", "me", "mi", "mis", "mía",
    "mías", "mío", "míos", "mucha", "muchas", "mucho", "muchos", "muy",
    "nada", "ni", "no", "nos", "nosotras", "nosotros", "nuestra", "nuestras",
    "nuestro", "nuestros", "o", "os", "otra", "otras", "otro", "otros",
    "para", "pero", "poco", "por", "porque", "que", "qué", "se", "sea",
    "sean", "ser", "si", "sí", "sin", "sobre", "sois", "somos", "son",
    "soy", "su", "sus", "suya", "suyas", "suyo", "suyos", "también",
    "tanto", "te", "tenéis", "tenemos", "tener", "tengo", "ti", "tiene",
    "tienen", "todo", "todos", "tu", "tus", "un", "una", "uno", "unos",
    "vosotras", "vosotros", "vuestra", "vuestras", "vuestro", "vuestros",
    "y", "ya"
}


# =============================================================================
# LECTURA DE DATOS
# =============================================================================

def leer_archivo(ruta_archivo: str) -> pd.DataFrame:
    """
    Lee un archivo CSV o Excel exportado desde Google Forms.
    """
    ruta = Path(ruta_archivo)

    if not ruta.exists():
        raise FileNotFoundError(f"No se encuentra el archivo: {ruta_archivo}")

    extension = ruta.suffix.lower()

    if extension == ".csv":
        try:
            return pd.read_csv(ruta, encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(ruta, encoding="latin-1")

    if extension in [".xlsx", ".xls"]:
        return pd.read_excel(ruta)

    raise ValueError("Formato no soportado. Usa CSV, XLSX o XLS.")


def detectar_columna_abierta(df: pd.DataFrame) -> str:
    """
    Intenta detectar automáticamente la columna de respuesta abierta.

    Busca columnas textuales que contengan términos habituales en preguntas abiertas
    de evaluación: opinión, experiencia, gustado, mejorarías, comentario, etc.
    """
    keywords = [
        "opinión", "opinion", "experiencia", "gustado", "gustó", "gusto",
        "mejorar", "mejorarías", "mejorarias", "comentario", "final",
        "cuéntanos", "cuentanos", "qué te ha gustado", "que te ha gustado"
    ]

    columnas_texto = []
    for col in df.columns:
        if df[col].dtype == "object":
            serie = df[col].dropna().astype(str)
            if len(serie) > 0:
                longitud_media = serie.str.len().mean()
                columnas_texto.append((col, longitud_media))

    if not columnas_texto:
        raise ValueError("No se han encontrado columnas de texto en el archivo.")

    puntuaciones = []

    for col, longitud_media in columnas_texto:
        col_lower = col.lower()
        score = 0

        for kw in keywords:
            if kw in col_lower:
                score += 10

        # Una pregunta abierta suele tener respuestas más largas.
        if longitud_media > 40:
            score += 3
        if longitud_media > 80:
            score += 5

        puntuaciones.append((col, score, longitud_media))

    puntuaciones = sorted(puntuaciones, key=lambda x: (x[1], x[2]), reverse=True)

    mejor_columna, mejor_score, _ = puntuaciones[0]

    print("\nColumna abierta detectada automáticamente:")
    print(f"  -> {mejor_columna}")

    print("\nColumnas textuales candidatas:")
    for col, score, long_media in puntuaciones:
        print(f"  - {col} | score={score} | longitud_media={long_media:.1f}")

    if mejor_score == 0:
        print(
            "\nAviso: la detección automática no está muy segura. "
            "Puedes indicar la columna manualmente con --columna."
        )

    return mejor_columna


# =============================================================================
# LIMPIEZA Y PREPROCESAMIENTO
# =============================================================================

def cargar_spacy():
    """
    Intenta cargar spaCy con modelo español.

    Si no está instalado el modelo, el script seguirá funcionando sin lematización.
    """
    try:
        import spacy
        nlp = spacy.load("es_core_news_sm", disable=["parser", "ner"])
        return nlp
    except Exception:
        return None


def obtener_stopwords(nlp=None, idioma="spanish") -> set:
    """
    Obtiene stopwords en español usando spaCy si está disponible.
    Si no, usa una lista interna básica.
    """
    stopwords = set(STOPWORDS_ES_FALLBACK)

    if nlp is not None:
        try:
            stopwords = set(nlp.Defaults.stop_words)
        except Exception:
            pass

    # Conservamos términos importantes del dominio aunque aparezcan en stopwords.
    stopwords = stopwords - PALABRAS_RELEVANTES

    return stopwords


def limpiar_texto_basico(texto: str) -> str:
    """
    Limpieza básica:
    - minúsculas;
    - eliminación de URLs;
    - eliminación de signos innecesarios;
    - normalización de espacios.
    """
    texto = str(texto).lower()
    texto = re.sub(r"http\S+|www\S+", " ", texto)
    texto = re.sub(r"[^a-záéíóúüñ0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def preprocesar_textos(textos, idioma="spanish"):
    """
    Limpia, elimina stopwords y lematiza si spaCy está disponible.

    Devuelve:
    - textos_limpios: lista de textos procesados;
    - stopwords: conjunto de stopwords usadas;
    - uso_spacy: bool indicando si se usó lematización.
    """
    nlp = cargar_spacy()
    stopwords = obtener_stopwords(nlp, idioma=idioma)

    textos_basicos = [limpiar_texto_basico(t) for t in textos]

    if nlp is None:
        print(
            "\nAviso: spaCy o el modelo es_core_news_sm no está disponible. "
            "Se hará limpieza sin lematización."
        )

        textos_limpios = []
        for texto in textos_basicos:
            tokens = texto.split()
            tokens = [
                tok for tok in tokens
                if (tok not in stopwords or tok in PALABRAS_RELEVANTES)
                and (len(tok) > 2 or tok in PALABRAS_RELEVANTES)
            ]
            textos_limpios.append(" ".join(tokens))

        return textos_limpios, stopwords, False

    textos_limpios = []

    for doc in nlp.pipe(textos_basicos):
        tokens = []

        for token in doc:
            tok = token.text.lower().strip()
            lemma = token.lemma_.lower().strip()

            if not tok:
                continue

            if not token.is_alpha:
                continue

            if tok in PALABRAS_RELEVANTES:
                tokens.append(tok)
                continue

            if lemma in PALABRAS_RELEVANTES:
                tokens.append(lemma)
                continue

            if tok in stopwords or lemma in stopwords:
                continue

            if len(lemma) <= 2:
                continue

            tokens.append(lemma)

        textos_limpios.append(" ".join(tokens))

    return textos_limpios, stopwords, True


# =============================================================================
# ANÁLISIS DESCRIPTIVO
# =============================================================================

def obtener_palabras_frecuentes(textos_limpios, top_n=30) -> pd.DataFrame:
    """
    Calcula las palabras más frecuentes del corpus limpio.
    """
    contador = Counter()

    for texto in textos_limpios:
        contador.update(texto.split())

    datos = contador.most_common(top_n)

    return pd.DataFrame(datos, columns=["palabra", "frecuencia"])


def obtener_ngramas_frecuentes(textos_limpios, ngram_range=(2, 3), top_n=30) -> pd.DataFrame:
    """
    Calcula bigramas y trigramas frecuentes sobre el texto limpio.
    """
    textos_validos = [t for t in textos_limpios if len(t.split()) >= 2]

    if not textos_validos:
        return pd.DataFrame(columns=["ngrama", "frecuencia"])

    vectorizer = CountVectorizer(ngram_range=ngram_range, min_df=1)
    X = vectorizer.fit_transform(textos_validos)

    frecuencias = np.asarray(X.sum(axis=0)).ravel()
    terminos = vectorizer.get_feature_names_out()

    df_ngramas = pd.DataFrame({
        "ngrama": terminos,
        "frecuencia": frecuencias
    }).sort_values("frecuencia", ascending=False).head(top_n)

    return df_ngramas.reset_index(drop=True)


def analisis_descriptivo(df: pd.DataFrame, columna: str, textos_limpios) -> dict:
    """
    Genera métricas descriptivas iniciales.
    """
    respuestas = df[columna].dropna().astype(str)
    longitudes = respuestas.str.split().apply(len)

    descriptivo = {
        "numero_respuestas": len(respuestas),
        "longitud_media_palabras": float(longitudes.mean()) if len(longitudes) else 0,
        "longitud_mediana_palabras": float(longitudes.median()) if len(longitudes) else 0,
        "longitud_minima_palabras": int(longitudes.min()) if len(longitudes) else 0,
        "longitud_maxima_palabras": int(longitudes.max()) if len(longitudes) else 0,
        "numero_respuestas_vacias_tras_limpieza": int(sum(1 for t in textos_limpios if not t.strip()))
    }

    return descriptivo


# =============================================================================
# MODELADO DE TEMAS: BERTopic O NMF
# =============================================================================

def interpretar_tema(palabras_clave: str) -> str:
    """
    Genera una interpretación automática sencilla a partir de las palabras clave.
    Está pensada como ayuda inicial para el TFM, no como sustituto de revisión humana.
    """
    texto = palabras_clave.lower()

    reglas = [
        (
            ["calendario", "disponibilidad", "fecha", "fechas", "ocupado", "libre"],
            "Tema relacionado con calendario, fechas y disponibilidad del alojamiento."
        ),
        (
            ["reserva", "reservar", "confirmación", "confirmar", "modificar", "cancelar", "formulario", "flujo"],
            "Tema relacionado con el flujo de reserva, confirmación o gestión de reservas."
        ),
        (
            ["bot", "asistente", "respuesta", "información", "duda", "pregunta", "chat"],
            "Tema relacionado con la utilidad, claridad o precisión de las respuestas del asistente conversacional."
        ),
        (
            ["diseño", "interfaz", "visual", "estética", "pantalla", "menú", "botón", "movil", "móvil"],
            "Tema relacionado con diseño, interfaz, navegación o experiencia visual."
        ),
        (
            ["rapidez", "rápido", "lento", "fluidez", "carga", "velocidad", "espera"],
            "Tema relacionado con rapidez, rendimiento o fluidez de uso."
        ),
        (
            ["precio", "precios", "descuento", "descuentos", "pricing", "tarifa", "coste"],
            "Tema relacionado con precios, descuentos o transparencia económica."
        ),
        (
            ["confianza", "seguridad", "real", "transparente", "email", "correo"],
            "Tema relacionado con confianza, seguridad o transparencia del proceso."
        ),
        (
            ["meteorología", "tiempo", "clima", "lluvia", "temperatura"],
            "Tema relacionado con la funcionalidad de meteorología o información contextual del destino."
        ),
        (
            ["panel", "admin", "administración", "métricas", "tabla"],
            "Tema relacionado con el panel de administración y la visualización de métricas o reservas."
        )
    ]

    interpretaciones = []
    for keywords, interpretacion in reglas:
        if any(k in texto for k in keywords):
            interpretaciones.append(interpretacion)

    if not interpretaciones:
        return "Tema general de experiencia de usuario. Requiere revisión manual de ejemplos representativos."

    return " ".join(interpretaciones)


def topic_modeling_bertopic(textos_originales, textos_limpios, stopwords, min_topic_size=2, nr_topics=None):
    """
    Aplica BERTopic si está instalado.

    Usa embeddings multilingües, adecuados para español y textos cortos.
    """
    from bertopic import BERTopic
    from sentence_transformers import SentenceTransformer

    embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    vectorizer_model = CountVectorizer(
        stop_words=list(stopwords),
        ngram_range=(1, 2),
        min_df=1
    )

    if nr_topics is not None:
        try:
            nr_topics = int(nr_topics)
        except ValueError:
            # BERTopic permite "auto".
            pass

    topic_model = BERTopic(
        language="multilingual",
        embedding_model=embedding_model,
        vectorizer_model=vectorizer_model,
        min_topic_size=min_topic_size,
        nr_topics=nr_topics,
        calculate_probabilities=False,
        verbose=False
    )

    topics, _ = topic_model.fit_transform(textos_originales)

    df_respuestas = pd.DataFrame({
        "respuesta_original": textos_originales,
        "texto_limpio": textos_limpios,
        "tema_id": topics
    })

    filas_temas = []

    for tema_id in sorted(set(topics)):
        subset = df_respuestas[df_respuestas["tema_id"] == tema_id]

        if tema_id == -1:
            palabras = "outliers / respuestas no agrupadas"
            nombre = "Tema -1: respuestas no agrupadas"
        else:
            topic_words = topic_model.get_topic(tema_id) or []
            palabras = ", ".join([w for w, _ in topic_words[:10]])
            nombre = f"Tema {tema_id}: {palabras.split(',')[0] if palabras else 'sin nombre'}"

        ejemplos = subset["respuesta_original"].head(3).tolist()

        filas_temas.append({
            "tema_id": tema_id,
            "nombre_tema": nombre,
            "n_respuestas": len(subset),
            "porcentaje": round(100 * len(subset) / len(df_respuestas), 2),
            "palabras_clave": palabras,
            "interpretacion_automatica": interpretar_tema(palabras),
            "ejemplo_1": ejemplos[0] if len(ejemplos) > 0 else "",
            "ejemplo_2": ejemplos[1] if len(ejemplos) > 1 else "",
            "ejemplo_3": ejemplos[2] if len(ejemplos) > 2 else ""
        })

    df_temas = pd.DataFrame(filas_temas).sort_values("n_respuestas", ascending=False)

    return df_temas, df_respuestas, topic_model


def topic_modeling_nmf(textos_originales, textos_limpios, n_topics=5):
    """
    Alternativa robusta: TF-IDF + NMF.

    Es más simple que BERTopic, pero muy interpretable para memoria académica.
    Funciona bien en corpus pequeños si se ajusta un número razonable de temas.
    """
    textos_validos = []
    indices_validos = []

    for i, texto in enumerate(textos_limpios):
        if texto.strip():
            textos_validos.append(texto)
            indices_validos.append(i)

    if len(textos_validos) < 2:
        raise ValueError("No hay suficientes respuestas válidas para aplicar topic modeling.")

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
        sublinear_tf=True
    )

    X = vectorizer.fit_transform(textos_validos)
    terminos = vectorizer.get_feature_names_out()

    n_topics_ajustado = min(
        int(n_topics),
        X.shape[0],
        X.shape[1]
    )

    n_topics_ajustado = max(1, n_topics_ajustado)

    nmf = NMF(
        n_components=n_topics_ajustado,
        random_state=42,
        init="nndsvda",
        max_iter=1000
    )

    W = nmf.fit_transform(X)
    H = nmf.components_

    temas_asignados_validos = W.argmax(axis=1)

    tema_por_indice = {idx: tema for idx, tema in zip(indices_validos, temas_asignados_validos)}

    temas_asignados = []
    for i in range(len(textos_limpios)):
        temas_asignados.append(tema_por_indice.get(i, -1))

    df_respuestas = pd.DataFrame({
        "respuesta_original": textos_originales,
        "texto_limpio": textos_limpios,
        "tema_id": temas_asignados
    })

    filas_temas = []

    for tema_id in sorted(set(temas_asignados)):
        subset = df_respuestas[df_respuestas["tema_id"] == tema_id]

        if tema_id == -1:
            palabras = "respuesta vacía tras limpieza"
            nombre = "Tema -1: sin asignar"
            ejemplos = subset["respuesta_original"].head(3).tolist()
        else:
            indices_top = H[tema_id].argsort()[::-1][:10]
            palabras_top = [terminos[i] for i in indices_top]
            palabras = ", ".join(palabras_top)
            nombre = f"Tema {tema_id}: {palabras_top[0] if palabras_top else 'sin nombre'}"

            # Ejemplos representativos: respuestas con mayor peso en ese tema.
            indices_docs_tema = np.where(temas_asignados_validos == tema_id)[0]
            pesos_tema = W[indices_docs_tema, tema_id]
            orden = indices_docs_tema[np.argsort(pesos_tema)[::-1]]

            ejemplos = []
            for pos in orden[:3]:
                idx_original = indices_validos[pos]
                ejemplos.append(textos_originales[idx_original])

        filas_temas.append({
            "tema_id": tema_id,
            "nombre_tema": nombre,
            "n_respuestas": len(subset),
            "porcentaje": round(100 * len(subset) / len(df_respuestas), 2),
            "palabras_clave": palabras,
            "interpretacion_automatica": interpretar_tema(palabras),
            "ejemplo_1": ejemplos[0] if len(ejemplos) > 0 else "",
            "ejemplo_2": ejemplos[1] if len(ejemplos) > 1 else "",
            "ejemplo_3": ejemplos[2] if len(ejemplos) > 2 else ""
        })

    df_temas = pd.DataFrame(filas_temas).sort_values("n_respuestas", ascending=False)

    return df_temas, df_respuestas, nmf


def ejecutar_topic_modeling(
    textos_originales,
    textos_limpios,
    stopwords,
    metodo="auto",
    n_topics=5,
    min_topic_size=2,
    nr_topics_bertopic=None
):
    """
    Ejecuta BERTopic si se solicita o si metodo='auto'.
    Si BERTopic falla, pasa automáticamente a NMF.
    """
    metodo_usado = None
    modelo = None

    if metodo in ["auto", "bertopic"]:
        try:
            print("\nIntentando topic modeling con BERTopic...")
            df_temas, df_respuestas, modelo = topic_modeling_bertopic(
                textos_originales=textos_originales,
                textos_limpios=textos_limpios,
                stopwords=stopwords,
                min_topic_size=min_topic_size,
                nr_topics=nr_topics_bertopic
            )
            metodo_usado = "BERTopic"
            print("BERTopic ejecutado correctamente.")
            return df_temas, df_respuestas, modelo, metodo_usado

        except Exception as e:
            print("\nNo se pudo ejecutar BERTopic.")
            print(f"Motivo: {e}")

            if metodo == "bertopic":
                raise

            print("Se usará la alternativa TF-IDF + NMF.")

    print("\nEjecutando topic modeling con TF-IDF + NMF...")
    df_temas, df_respuestas, modelo = topic_modeling_nmf(
        textos_originales=textos_originales,
        textos_limpios=textos_limpios,
        n_topics=n_topics
    )
    metodo_usado = "TF-IDF + NMF"

    return df_temas, df_respuestas, modelo, metodo_usado


# =============================================================================
# MEJORAS PRIORIZADAS
# =============================================================================

def generar_mejoras_priorizadas(df_respuestas: pd.DataFrame) -> pd.DataFrame:
    """
    Genera una tabla de mejoras accionables priorizadas por frecuencia de mención.

    La lógica combina:
    - frecuencia de menciones de cada categoría;
    - porcentaje de menciones con términos de fricción o mejora;
    - propuesta accionable asociada.
    """

    categorias = {
        "Calendario y disponibilidad": {
            "keywords": [
                "calendario", "disponibilidad", "fecha", "fechas",
                "libre", "ocupado", "ocupada", "noche", "día", "dias", "días"
            ],
            "propuesta": (
                "Reforzar la claridad visual del calendario, mostrar estados de disponibilidad "
                "con más evidencia y explicar mejor cómo se seleccionan fechas."
            )
        },
        "Flujo de reserva": {
            "keywords": [
                "reserva", "reservar", "confirmación", "confirmar", "formulario",
                "paso", "pasos", "modificar", "cancelar", "gestión"
            ],
            "propuesta": (
                "Simplificar el flujo de reserva, añadir mensajes de confirmación más claros "
                "y destacar las opciones de modificación o cancelación."
            )
        },
        "Asistente conversacional": {
            "keywords": [
                "bot", "asistente", "respuesta", "respuestas", "información",
                "duda", "pregunta", "chat", "rag", "consulta"
            ],
            "propuesta": (
                "Mejorar la cobertura de respuestas del asistente, añadir ejemplos de preguntas "
                "y reforzar mensajes cuando no tenga suficiente información."
            )
        },
        "Diseño e interfaz": {
            "keywords": [
                "diseño", "interfaz", "visual", "estética", "pantalla",
                "menú", "botón", "botones", "navegación", "móvil", "movil"
            ],
            "propuesta": (
                "Pulir jerarquía visual, botones principales, legibilidad y adaptación móvil "
                "para reducir fricción de navegación."
            )
        },
        "Rapidez y rendimiento": {
            "keywords": [
                "rapidez", "rápido", "rapido", "fluidez", "lento", "lenta",
                "carga", "velocidad", "espera", "tarda", "tardar"
            ],
            "propuesta": (
                "Optimizar tiempos de carga, respuestas del bot y transiciones entre pasos clave."
            )
        },
        "Precios y descuentos": {
            "keywords": [
                "precio", "precios", "descuento", "descuentos", "pricing",
                "tarifa", "coste", "importe", "total", "dinámico", "dinamico"
            ],
            "propuesta": (
                "Explicar mejor el cálculo del precio final, descuentos aplicados y condiciones "
                "del pricing dinámico."
            )
        },
        "Confianza y transparencia": {
            "keywords": [
                "confianza", "seguridad", "seguro", "real", "transparente",
                "correo", "email", "confirmación", "datos"
            ],
            "propuesta": (
                "Añadir señales de confianza: confirmaciones claras, resumen final de reserva, "
                "datos del alojamiento y mensajes de seguridad."
            )
        },
        "Meteorología": {
            "keywords": [
                "meteorología", "meteorologia", "tiempo", "clima", "lluvia",
                "temperatura", "previsión", "prevision"
            ],
            "propuesta": (
                "Integrar la meteorología de forma contextual, por ejemplo vinculada a la estancia "
                "o a recomendaciones para Toledo/Cobisa."
            )
        },
        "Panel de administración": {
            "keywords": [
                "panel", "admin", "administración", "administracion",
                "métricas", "metricas", "tabla", "reservas"
            ],
            "propuesta": (
                "Mejorar la lectura de métricas, filtros de reservas y visibilidad de acciones "
                "administrativas."
            )
        }
    }

    terminos_friccion = [
        "mejorar", "mejoraría", "mejoraria", "falta", "faltaría", "faltaria",
        "confuso", "confusa", "difícil", "dificil", "lento", "lenta",
        "problema", "error", "no", "añadir", "agregar", "eché en falta",
        "eché en falta", "podría", "podria", "debería", "deberia"
    ]

    total_respuestas = len(df_respuestas)
    filas = []

    for categoria, info in categorias.items():
        keywords = info["keywords"]
        propuesta = info["propuesta"]

        menciones = 0
        menciones_friccion = 0
        ejemplos = []

        for _, row in df_respuestas.iterrows():
            texto = f"{row.get('respuesta_original', '')} {row.get('texto_limpio', '')}".lower()

            aparece_categoria = any(k.lower() in texto for k in keywords)

            if aparece_categoria:
                menciones += 1

                if len(ejemplos) < 3:
                    ejemplos.append(row.get("respuesta_original", ""))

                if any(t in texto for t in terminos_friccion):
                    menciones_friccion += 1

        if menciones > 0:
            porcentaje = round(100 * menciones / total_respuestas, 2)
            friccion_pct = round(100 * menciones_friccion / menciones, 2)

            # Puntuación simple de prioridad:
            # más frecuencia + más proporción de fricción = más prioridad.
            prioridad_score = round(menciones * (1 + menciones_friccion / max(menciones, 1)), 2)

            filas.append({
                "categoria_mejora": categoria,
                "frecuencia_menciones": menciones,
                "porcentaje_respuestas": porcentaje,
                "menciones_con_friccion_o_mejora": menciones_friccion,
                "porcentaje_friccion_dentro_categoria": friccion_pct,
                "priority_score": prioridad_score,
                "propuesta_accionable": propuesta,
                "ejemplo_1": ejemplos[0] if len(ejemplos) > 0 else "",
                "ejemplo_2": ejemplos[1] if len(ejemplos) > 1 else "",
                "ejemplo_3": ejemplos[2] if len(ejemplos) > 2 else ""
            })

    df_mejoras = pd.DataFrame(filas)

    if df_mejoras.empty:
        return pd.DataFrame(columns=[
            "categoria_mejora", "frecuencia_menciones", "porcentaje_respuestas",
            "menciones_con_friccion_o_mejora", "porcentaje_friccion_dentro_categoria",
            "priority_score", "propuesta_accionable", "ejemplo_1", "ejemplo_2", "ejemplo_3"
        ])

    return df_mejoras.sort_values(
        ["priority_score", "frecuencia_menciones"],
        ascending=False
    ).reset_index(drop=True)


# =============================================================================
# AGRUPACIÓN MANUAL DE TEMAS
# =============================================================================

def agrupar_temas_manualmente(df_respuestas: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    Permite agrupar manualmente temas similares.

    Ejemplo:
    mapping = {
        "Reserva y disponibilidad": [0, 2],
        "Diseño y navegación": [1, 4],
        "Asistente": [3]
    }

    Esto resulta útil si BERTopic o NMF separan temas que, para la memoria del TFM,
    se quieren interpretar como una misma dimensión de experiencia de usuario.
    """
    df = df_respuestas.copy()

    def asignar_grupo(tema_id):
        for nombre_grupo, lista_temas in mapping.items():
            if tema_id in lista_temas:
                return nombre_grupo
        return f"Sin agrupar / tema {tema_id}"

    df["grupo_manual"] = df["tema_id"].apply(asignar_grupo)

    return df


# =============================================================================
# VISUALIZACIONES
# =============================================================================

def guardar_grafico_frecuencia_temas(df_temas: pd.DataFrame, output_dir: str):
    """
    Guarda gráfico de barras con frecuencia de temas.
    """
    if df_temas.empty:
        return

    df_plot = df_temas.copy()
    df_plot["tema_label"] = df_plot["tema_id"].astype(str) + " - " + df_plot["nombre_tema"].astype(str)

    plt.figure(figsize=(10, 6))
    plt.barh(df_plot["tema_label"], df_plot["n_respuestas"])
    plt.xlabel("Número de respuestas")
    plt.ylabel("Tema")
    plt.title("Frecuencia de temas detectados")
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "frecuencia_temas.png"), dpi=300)
    plt.close()


def guardar_grafico_palabras_frecuentes(df_palabras: pd.DataFrame, output_dir: str):
    """
    Guarda gráfico de barras con palabras más frecuentes.
    """
    if df_palabras.empty:
        return

    df_plot = df_palabras.sort_values("frecuencia", ascending=True)

    plt.figure(figsize=(10, 7))
    plt.barh(df_plot["palabra"], df_plot["frecuencia"])
    plt.xlabel("Frecuencia")
    plt.ylabel("Palabra")
    plt.title("Palabras más frecuentes en respuestas abiertas")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "palabras_frecuentes.png"), dpi=300)
    plt.close()


def guardar_nube_palabras(textos_limpios, output_dir: str):
    """
    Guarda una nube de palabras general.
    Requiere instalar wordcloud.
    """
    try:
        from wordcloud import WordCloud
    except Exception:
        print("\nAviso: wordcloud no está instalado. No se generará nube de palabras.")
        return

    texto_total = " ".join(textos_limpios).strip()

    if not texto_total:
        return

    wc = WordCloud(
        width=1200,
        height=700,
        background_color="white",
        collocations=False
    ).generate(texto_total)

    plt.figure(figsize=(12, 7))
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.title("Nube de palabras general")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "nube_palabras.png"), dpi=300)
    plt.close()


# =============================================================================
# INFORME MARKDOWN
# =============================================================================

def guardar_informe_markdown(
    output_dir,
    descriptivo,
    metodo_usado,
    uso_spacy,
    columna,
    df_temas,
    df_palabras,
    df_ngramas,
    df_mejoras
):
    """
    Genera un informe Markdown resumido para poder trasladarlo a la memoria del TFM.
    """
    ruta = os.path.join(output_dir, "informe_resumen_topic_modeling.md")

    with open(ruta, "w", encoding="utf-8") as f:
        f.write("# Informe de topic modeling sobre respuestas abiertas\n\n")

        f.write("## 1. Contexto\n\n")
        f.write(
            "Este análisis se ha realizado sobre las respuestas abiertas del formulario "
            "de evaluación de usuarios del TFM. El objetivo es identificar temas recurrentes "
            "relacionados con la experiencia de uso de la web, el asistente conversacional, "
            "el flujo de reserva, el diseño, la rapidez, la disponibilidad, los precios y "
            "otras funcionalidades del sistema.\n\n"
        )

        f.write("## 2. Configuración del análisis\n\n")
        f.write(f"- Columna analizada: `{columna}`\n")
        f.write(f"- Método de topic modeling usado: **{metodo_usado}**\n")
        f.write(f"- Lematización con spaCy: **{'sí' if uso_spacy else 'no'}**\n\n")

        f.write("## 3. Análisis descriptivo\n\n")
        for k, v in descriptivo.items():
            f.write(f"- {k}: {v}\n")

        f.write("\n## 4. Temas detectados\n\n")
        if df_temas.empty:
            f.write("No se detectaron temas.\n\n")
        else:
            for _, row in df_temas.iterrows():
                f.write(f"### Tema {row['tema_id']}: {row['nombre_tema']}\n\n")
                f.write(f"- Número de respuestas: {row['n_respuestas']}\n")
                f.write(f"- Porcentaje: {row['porcentaje']}%\n")
                f.write(f"- Palabras clave: {row['palabras_clave']}\n")
                f.write(f"- Interpretación automática: {row['interpretacion_automatica']}\n")
                f.write("- Ejemplos representativos:\n")
                for ej in [row.get("ejemplo_1", ""), row.get("ejemplo_2", ""), row.get("ejemplo_3", "")]:
                    if isinstance(ej, str) and ej.strip():
                        f.write(f"  - {ej}\n")
                f.write("\n")

        f.write("## 5. Palabras más frecuentes\n\n")
        if not df_palabras.empty:
            f.write(df_palabras.to_markdown(index=False))
            f.write("\n\n")

        f.write("## 6. Bigramas y trigramas frecuentes\n\n")
        if not df_ngramas.empty:
            f.write(df_ngramas.to_markdown(index=False))
            f.write("\n\n")

        f.write("## 7. Mejoras priorizadas\n\n")
        if df_mejoras.empty:
            f.write("No se detectaron categorías de mejora con las reglas actuales.\n\n")
        else:
            for _, row in df_mejoras.iterrows():
                f.write(f"### {row['categoria_mejora']}\n\n")
                f.write(f"- Frecuencia de menciones: {row['frecuencia_menciones']}\n")
                f.write(f"- Porcentaje de respuestas: {row['porcentaje_respuestas']}%\n")
                f.write(f"- Menciones con fricción o mejora: {row['menciones_con_friccion_o_mejora']}\n")
                f.write(f"- Puntuación de prioridad: {row['priority_score']}\n")
                f.write(f"- Propuesta accionable: {row['propuesta_accionable']}\n\n")

        f.write("## 8. Cómo interpretar los resultados en la memoria\n\n")
        f.write(
            "Los temas detectados deben interpretarse como agrupaciones exploratorias de "
            "opiniones de usuario. Para la memoria del TFM, se recomienda combinar la tabla "
            "de temas con ejemplos textuales representativos y con la tabla de mejoras "
            "priorizadas. La interpretación automática puede utilizarse como punto de partida, "
            "pero conviene revisarla manualmente para asegurar que cada tema queda descrito "
            "de forma fiel al contenido de las respuestas.\n"
        )


# =============================================================================
# PIPELINE PRINCIPAL
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Análisis de topic modeling sobre respuestas abiertas de Google Forms."
    )

    parser.add_argument(
        "--archivo",
        required=True,
        help="Ruta del archivo CSV o Excel exportado desde Google Forms."
    )

    parser.add_argument(
        "--columna",
        default=None,
        help="Nombre exacto de la columna de respuesta abierta. Si no se indica, se intenta detectar."
    )

    parser.add_argument(
        "--metodo",
        default="auto",
        choices=["auto", "bertopic", "nmf"],
        help="Método de topic modeling. auto intenta BERTopic y si falla usa NMF."
    )

    parser.add_argument(
        "--n_topics",
        type=int,
        default=5,
        help="Número de temas para NMF."
    )

    parser.add_argument(
        "--min_topic_size",
        type=int,
        default=2,
        help="Tamaño mínimo de tema para BERTopic. En corpus pequeños se recomienda 2."
    )

    parser.add_argument(
        "--nr_topics_bertopic",
        default=None,
        help="Número de temas para BERTopic. Puede ser un entero o 'auto'."
    )

    parser.add_argument(
        "--idioma_stopwords",
        default="spanish",
        help="Idioma de stopwords. Por defecto: spanish."
    )

    args = parser.parse_args()

    warnings.filterwarnings("ignore")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\nLeyendo archivo...")
    df = leer_archivo(args.archivo)

    print(f"Archivo cargado correctamente. Filas: {df.shape[0]}, columnas: {df.shape[1]}")

    if args.columna is None:
        columna_abierta = detectar_columna_abierta(df)
    else:
        columna_abierta = args.columna
        if columna_abierta not in df.columns:
            raise ValueError(
                f"La columna indicada no existe: {columna_abierta}\n"
                f"Columnas disponibles: {list(df.columns)}"
            )

    df = df.copy()
    df[columna_abierta] = df[columna_abierta].fillna("").astype(str)

    # Eliminamos respuestas completamente vacías.
    df_analisis = df[df[columna_abierta].str.strip() != ""].copy()

    if df_analisis.empty:
        raise ValueError("No hay respuestas abiertas válidas para analizar.")

    textos_originales = df_analisis[columna_abierta].tolist()

    print("\nPreprocesando textos...")
    textos_limpios, stopwords, uso_spacy = preprocesar_textos(
        textos_originales,
        idioma=args.idioma_stopwords
    )

    df_analisis["texto_limpio"] = textos_limpios

    print("\nGenerando análisis descriptivo...")
    descriptivo = analisis_descriptivo(df_analisis, columna_abierta, textos_limpios)

    df_palabras = obtener_palabras_frecuentes(textos_limpios, top_n=30)
    df_ngramas = obtener_ngramas_frecuentes(textos_limpios, ngram_range=(2, 3), top_n=30)

    print("\nResumen descriptivo:")
    for k, v in descriptivo.items():
        print(f"  - {k}: {v}")

    print("\nEjecutando topic modeling...")
    df_temas, df_respuestas, modelo, metodo_usado = ejecutar_topic_modeling(
        textos_originales=textos_originales,
        textos_limpios=textos_limpios,
        stopwords=stopwords,
        metodo=args.metodo,
        n_topics=args.n_topics,
        min_topic_size=args.min_topic_size,
        nr_topics_bertopic=args.nr_topics_bertopic
    )

    print("\nGenerando mejoras priorizadas...")
    df_mejoras = generar_mejoras_priorizadas(df_respuestas)

    print("\nGuardando resultados...")
    df_temas.to_csv(os.path.join(OUTPUT_DIR, "temas_detectados.csv"), index=False, encoding="utf-8-sig")
    df_respuestas.to_csv(os.path.join(OUTPUT_DIR, "respuestas_con_tema.csv"), index=False, encoding="utf-8-sig")
    df_mejoras.to_csv(os.path.join(OUTPUT_DIR, "mejoras_priorizadas.csv"), index=False, encoding="utf-8-sig")
    df_palabras.to_csv(os.path.join(OUTPUT_DIR, "palabras_frecuentes.csv"), index=False, encoding="utf-8-sig")
    df_ngramas.to_csv(os.path.join(OUTPUT_DIR, "ngramas_frecuentes.csv"), index=False, encoding="utf-8-sig")

    guardar_grafico_frecuencia_temas(df_temas, OUTPUT_DIR)
    guardar_grafico_palabras_frecuentes(df_palabras, OUTPUT_DIR)
    guardar_nube_palabras(textos_limpios, OUTPUT_DIR)

    guardar_informe_markdown(
        output_dir=OUTPUT_DIR,
        descriptivo=descriptivo,
        metodo_usado=metodo_usado,
        uso_spacy=uso_spacy,
        columna=columna_abierta,
        df_temas=df_temas,
        df_palabras=df_palabras,
        df_ngramas=df_ngramas,
        df_mejoras=df_mejoras
    )

    print("\nProceso finalizado correctamente.")
    print(f"Resultados guardados en: {OUTPUT_DIR}/")

    print("\nArchivos principales generados:")
    print("  - temas_detectados.csv")
    print("  - respuestas_con_tema.csv")
    print("  - mejoras_priorizadas.csv")
    print("  - palabras_frecuentes.csv")
    print("  - ngramas_frecuentes.csv")
    print("  - frecuencia_temas.png")
    print("  - palabras_frecuentes.png")
    print("  - nube_palabras.png, si wordcloud está instalado")
    print("  - informe_resumen_topic_modeling.md")


if __name__ == "__main__":
    main()