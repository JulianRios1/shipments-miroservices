from PIL import Image, ImageDraw, ImageFont
import os

def generar_imagenes_con_texto(textos_array, ruta_destino=None, ancho=800, alto=400, tamano_fuente=40):
    """
    Genera imágenes PNG con texto en fondo blanco y letra negra
    
    Parámetros:
    - textos_array: Lista de strings con los textos a convertir en imágenes
    - ruta_destino: Ruta completa donde se guardarán las imágenes (ej: "C:/mis_imagenes" o "/home/usuario/imagenes")
    - ancho, alto: Dimensiones de la imagen
    - tamano_fuente: Tamaño de la fuente
    """
    
    # Si no se especifica ruta, usar directorio actual
    if ruta_destino is None:
        ruta_destino = os.path.join(os.getcwd(), "imagenes_generadas")
    
    # Crear directorio de salida si no existe
    if not os.path.exists(ruta_destino):
        os.makedirs(ruta_destino)
        print(f"Creado directorio: {ruta_destino}")
    
    # Intentar cargar una fuente del sistema, si no usar la por defecto
    try:
        # Para Windows
        fuente = ImageFont.truetype("arial.ttf", tamano_fuente)
    except:
        try:
            # Para Linux/Mac
            fuente = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", tamano_fuente)
        except:
            # Fuente por defecto si no encuentra ninguna
            fuente = ImageFont.load_default()
    
    for i, texto in enumerate(textos_array):
        # Crear imagen con fondo blanco
        imagen = Image.new('RGB', (ancho, alto), color='white')
        
        # Crear objeto para dibujar
        draw = ImageDraw.Draw(imagen)
        
        # Calcular posición para centrar el texto
        bbox = draw.textbbox((0, 0), texto, font=fuente)
        texto_ancho = bbox[2] - bbox[0]
        texto_alto = bbox[3] - bbox[1]
        
        x = (ancho - texto_ancho) // 2
        y = (alto - texto_alto) // 2
        
        # Dibujar el texto en negro
        draw.text((x, y), texto, fill='black', font=fuente)
        
        # Generar nombre del archivo (sanitizar el texto para nombre de archivo)
        nombre_archivo = f"{sanitizar_nombre(texto)}.png"
        ruta_completa = os.path.join(ruta_destino, nombre_archivo)
        
        # Guardar la imagen
        imagen.save(ruta_completa, 'PNG')
        print(f"INSERT INTO public.envios_imagen (usuario_id, idenvio, ruta, deleted_at, created_at, updated_at, modulo, img_despacho) VALUES({texto},'{nombre_archivo}', NULL, now(),now(), 'cloud', false);\n")

def sanitizar_nombre(texto):
    """
    Limpia el texto para que sea válido como nombre de archivo
    """
    # Reemplazar caracteres problemáticos
    caracteres_invalidos = '<>:"/\\|?*'
    nombre_limpio = texto
    
    for char in caracteres_invalidos:
        nombre_limpio = nombre_limpio.replace(char, '_')
    
    # Limitar longitud y quitar espacios extra
    nombre_limpio = nombre_limpio.strip().replace(' ', '_')[:50]
    
    return nombre_limpio

# Ejemplo de uso
if __name__ == "__main__":
    # Array de textos de ejemplo
    textos_ejemplo = [
        "85910403101791",
        "85910403101792",
        "85910403101795",
        "85910403101812",
        "85910403101815",
        "85910403101816",
        "85910403101818",
        "85910403101819",
        "85910403101820",
        "85910403101821",
        "85910403101822",
        "85910403101823",
        "85910403101824",
        "85910403101825",
        "85910403101826",
        "85910403101827",
        "85910403101829",
        "85910403101831",
        "85910403101834",
        "85910403101835",
        "85910403101836",
        "85910403101837",
        "85910403101839",
        "85910403101841",
        "85910403101843",
        "85910403101862",
        "85910403121972",
        "85910403121973",
        "85910403121974",
        "85910403121975",
        "85910403124977",
        "85910403124978",
        "85910403124979",
        "85910403124980",
        "85910403125202",
        "85910403125307",
        "85910403128485",
        "85910403128486",
        "85910403128488",
        "85910403128487",
        "85910403128489",
        "85910403128490",
        "85910403128492",
        "85910403128493",
        "85910403128494",
        "85910403128495",
        "85910403128497",
        "85910403128496",
        "85910403128498",
        "85910403128499",
        "85910403128500",
        "85910403128501",
        "85910403128503",
        "85910403128504",
        "85910403128506",
        "85910403128516",
        "85910403128517",
        "85910403128518",
        "85910403128519",
        "85910403128520",
        "85910403128521",
        "85910403128720",
        "85910403128528",
        "85910403128532",
        "85910403128533",
        "85910403128534",
        "5104880019",
        "85910403128765",
        "85910403128766",
        "85910403128524",
        "85910403128526",
        "85910403128527"
    ]
    
    print("Iniciando generación de imágenes...")
    
    ruta_destino = None  # Se creará carpeta "imagenes_generadas" en el directorio actual
    
    # Generar las imágenes
    generar_imagenes_con_texto(
        textos_array=textos_ejemplo,
        ruta_destino='imagenes_de_prueba',
        ancho=400,
        alto=400,
        tamano_fuente=550
    )
    
    print("¡Generación completada!")
    print(f"Se generaron {len(textos_ejemplo)} imágenes en la ruta: {ruta_destino or 'imagenes_generadas'}")