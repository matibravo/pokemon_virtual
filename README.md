# Gengar Pet

Una mascota de escritorio hecha con Python y PyQt5. Se mueve por las esquinas
de la pantalla, reacciona al hacer clic y permite cambiar entre Gengar y
Charmander.

## Requisitos

- Python 3.10 o posterior
- Linux (el programa usa `fcntl`, que no está disponible en Windows)

## Instalación y ejecución

Desde la carpeta del proyecto, ejecuta:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python gengar.py
```

La primera ejecución requiere conexión a Internet para instalar PyQt5.

## Controles

- Clic izquierdo: hacer que la mascota reaccione.
- Doble clic izquierdo: cambiar entre Gengar y Charmander.
- Clic derecho: abrir el menú para contar un chiste, pausar o salir.

## Archivos de imagen

El programa necesita estos cuatro archivos en la misma carpeta que `gengar.py`:

- `gengar.png`
- `gengar_walk.gif`
- `charmander.png`
- `charmander_walk.gif`

