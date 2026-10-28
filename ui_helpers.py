import tkinter as tk
from tkinter import ttk


class BotonRedondeado(tk.Canvas):
    """Boton de accion redondeado compatible con las opciones de tk.Button."""

    def __init__(self, parent, text='', command=None, bg='#1B4965', fg='white',
                 font=('Segoe UI', 10, 'bold'), padx=15, pady=8,
                 width=None, height=None, **kwargs):
        ancho = width if isinstance(width, int) and width > 40 else max(120, len(text) * 8 + padx * 2)
        alto = height if isinstance(height, int) and height > 20 else max(38, pady * 2 + 20)
        super().__init__(
            parent, width=ancho, height=alto, bg=parent.cget('bg'),
            highlightthickness=0, bd=0, cursor='hand2'
        )
        self.command = command or (lambda: None)
        self.texto = text
        self.color = bg
        self.color_hover = self._oscurecer(bg)
        self.fuente = font
        self._dibujar(self.color)
        self.bind('<Enter>', lambda event: self._dibujar(self.color_hover))
        self.bind('<Leave>', lambda event: self._dibujar(self.color))
        self.bind('<Button-1>', lambda event: self.command())

    def _dibujar(self, color):
        self.delete('all')
        ancho = int(self['width'])
        alto = int(self['height'])
        radio = min(12, alto // 3)
        self.create_rectangle(radio, 0, ancho - radio, alto, fill=color, outline=color)
        self.create_rectangle(0, radio, ancho, alto - radio, fill=color, outline=color)
        for x, y, inicio in ((0, 0, 90), (ancho - 2 * radio, 0, 0),
                             (0, alto - 2 * radio, 180),
                             (ancho - 2 * radio, alto - 2 * radio, 270)):
            self.create_arc(x, y, x + 2 * radio, y + 2 * radio,
                            start=inicio, extent=90, fill=color, outline=color)
        self.create_text(ancho // 2, alto // 2, text=self.texto, fill='white', font=self.fuente)

    @staticmethod
    def _oscurecer(color):
        color = color.lstrip('#')
        rgb = [max(0, int(int(color[i:i + 2], 16) * 0.85)) for i in (0, 2, 4)]
        return '#' + ''.join(f'{valor:02x}' for valor in rgb)


class EntradaCuadrada(tk.Entry):
    """Campo de texto uniforme para todos los formularios del sistema."""

    def __init__(self, parent, **kwargs):
        kwargs.setdefault('font', ('Segoe UI', 10))
        kwargs.setdefault('bg', 'white')
        kwargs.setdefault('fg', '#183B56')
        kwargs.setdefault('insertbackground', '#183B56')
        kwargs.setdefault('relief', 'solid')
        kwargs.setdefault('bd', 1)
        kwargs.setdefault('highlightthickness', 1)
        kwargs.setdefault('highlightbackground', '#AEBBC5')
        kwargs.setdefault('highlightcolor', '#2B6384')
        super().__init__(parent, **kwargs)


def combo_busqueda(parent, valores, width=30):
    """Combobox editable que filtra opciones mientras se escribe."""
    combo = ttk.Combobox(parent, width=width, font=('Segoe UI', 10), state='normal')
    opciones = tuple(valores)
    combo['values'] = opciones
    if opciones:
        combo.current(0)

    def restaurar(event=None):
        combo['values'] = opciones

    def filtrar(event=None):
        if event and event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Escape', 'Tab'):
            return
        texto = combo.get().lower()
        combo['values'] = [valor for valor in opciones if texto in valor.lower()]

    combo.bind('<FocusIn>', restaurar)
    combo.bind('<KeyRelease>', filtrar)
    return combo
