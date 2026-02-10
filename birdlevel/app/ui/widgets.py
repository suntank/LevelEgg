"""Lightweight custom UI widgets for the editor, rendered with Pygame."""
from __future__ import annotations

from typing import Any, Callable

import pygame

from birdlevel.app.ui.theme import Theme


class UIEvent:
    """Simple event passed to widget callbacks."""
    def __init__(self, widget: Widget, data: Any = None):
        self.widget = widget
        self.data = data


class Widget:
    """Base class for all UI widgets."""

    def __init__(self, x: int = 0, y: int = 0, w: int = 100, h: int = 24):
        self.rect = pygame.Rect(x, y, w, h)
        self.visible = True
        self.enabled = True
        self._hovered = False
        self._focused = False
        self.parent: Widget | None = None
        self.children: list[Widget] = []
        self.tooltip: str = ""

    @property
    def abs_rect(self) -> pygame.Rect:
        if self.parent:
            pr = self.parent.abs_rect
            return pygame.Rect(pr.x + self.rect.x, pr.y + self.rect.y,
                               self.rect.w, self.rect.h)
        return self.rect

    def add_child(self, child: Widget) -> None:
        child.parent = self
        self.children.append(child)

    def hit_test(self, mx: int, my: int) -> bool:
        return self.visible and self.abs_rect.collidepoint(mx, my)

    def handle_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        """Handle input event. Return True if consumed."""
        if not self.visible or not self.enabled:
            return False
        for child in reversed(self.children):
            if child.handle_event(event, mx, my):
                return True
        return False

    def update_hover(self, mx: int, my: int) -> None:
        self._hovered = self.hit_test(mx, my)
        for child in self.children:
            child.update_hover(mx, my)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.visible:
            return
        for child in self.children:
            child.draw(surface, font)


class Panel(Widget):
    """A rectangular panel with background and optional title."""

    def __init__(self, x: int, y: int, w: int, h: int,
                 title: str = "", bg_color: tuple = Theme.BG_PANEL):
        super().__init__(x, y, w, h)
        self.title = title
        self.bg_color = bg_color
        self.scroll_y: int = 0
        self.content_height: int = 0
        self._dragging_scroll = False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.visible:
            return
        ar = self.abs_rect
        pygame.draw.rect(surface, self.bg_color, ar)
        pygame.draw.rect(surface, Theme.BORDER, ar, 1)

        y_off = 0
        if self.title:
            header_rect = pygame.Rect(ar.x, ar.y, ar.w, Theme.ITEM_HEIGHT)
            pygame.draw.rect(surface, Theme.BG_HEADER, header_rect)
            label = font.render(self.title, True, Theme.TEXT_BRIGHT)
            surface.blit(label, (ar.x + Theme.PANEL_PADDING, ar.y + 4))
            y_off = Theme.ITEM_HEIGHT

        # Clip children to panel area below title
        clip_rect = pygame.Rect(ar.x, ar.y + y_off, ar.w, ar.h - y_off)
        old_clip = surface.get_clip()
        surface.set_clip(clip_rect)

        for child in self.children:
            child.draw(surface, font)

        surface.set_clip(old_clip)

        # Scrollbar
        if self.content_height > ar.h - y_off:
            sb_x = ar.x + ar.w - Theme.SCROLLBAR_WIDTH
            sb_h = ar.h - y_off
            visible_ratio = sb_h / self.content_height
            thumb_h = max(20, int(sb_h * visible_ratio))
            max_scroll = self.content_height - sb_h
            scroll_ratio = min(1.0, self.scroll_y / max_scroll) if max_scroll > 0 else 0
            thumb_y = ar.y + y_off + int(scroll_ratio * (sb_h - thumb_h))
            pygame.draw.rect(surface, Theme.BG_INPUT,
                             (sb_x, ar.y + y_off, Theme.SCROLLBAR_WIDTH, sb_h))
            pygame.draw.rect(surface, Theme.BORDER_LIGHT,
                             (sb_x, thumb_y, Theme.SCROLLBAR_WIDTH, thumb_h))

    def handle_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        if not self.visible or not self.enabled:
            return False
        ar = self.abs_rect
        if event.type == pygame.MOUSEWHEEL and ar.collidepoint(mx, my):
            self.scroll_y = max(0, self.scroll_y - event.y * Theme.SCROLL_SPEED)
            return True
        return super().handle_event(event, mx, my)


class Button(Widget):
    """Clickable button with label."""

    def __init__(self, x: int, y: int, w: int, h: int = Theme.BUTTON_HEIGHT,
                 label: str = "", on_click: Callable | None = None,
                 toggle: bool = False):
        super().__init__(x, y, w, h)
        self.label = label
        self.on_click = on_click
        self.toggle = toggle
        self.toggled = False
        self._pressed = False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.visible:
            return
        ar = self.abs_rect
        if self.toggled:
            bg = Theme.BG_BUTTON_ACTIVE
        elif self._hovered:
            bg = Theme.BG_BUTTON_HOVER
        else:
            bg = Theme.BG_BUTTON
        pygame.draw.rect(surface, bg, ar, border_radius=3)
        pygame.draw.rect(surface, Theme.BORDER_LIGHT, ar, 1, border_radius=3)
        label = font.render(self.label, True, Theme.TEXT_BRIGHT if self.toggled else Theme.TEXT)
        lx = ar.x + (ar.w - label.get_width()) // 2
        ly = ar.y + (ar.h - label.get_height()) // 2
        surface.blit(label, (lx, ly))

    def handle_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.abs_rect.collidepoint(mx, my):
                self._pressed = True
                return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed and self.abs_rect.collidepoint(mx, my):
                self._pressed = False
                if self.toggle:
                    self.toggled = not self.toggled
                if self.on_click:
                    self.on_click(UIEvent(self))
                return True
            self._pressed = False
        return False


class Label(Widget):
    """Text label."""

    def __init__(self, x: int, y: int, text: str = "",
                 color: tuple = Theme.TEXT, max_width: int = 0):
        super().__init__(x, y, max_width or 200, Theme.ITEM_HEIGHT)
        self.text = text
        self.color = color

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.visible:
            return
        ar = self.abs_rect
        label = font.render(self.text, True, self.color)
        surface.blit(label, (ar.x, ar.y + 2))


class ListItem(Widget):
    """Selectable list item."""

    def __init__(self, x: int, y: int, w: int, text: str = "",
                 data: Any = None, on_select: Callable | None = None,
                 indicator_color: tuple | None = None):
        super().__init__(x, y, w, Theme.ITEM_HEIGHT)
        self.text = text
        self.data = data
        self.on_select = on_select
        self.selected = False
        self.indicator_color = indicator_color

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.visible:
            return
        ar = self.abs_rect
        if self.selected:
            pygame.draw.rect(surface, Theme.BG_SELECTED, ar)
        elif self._hovered:
            pygame.draw.rect(surface, Theme.BG_HOVER, ar)

        text_x = ar.x + Theme.PANEL_PADDING
        if self.indicator_color:
            ind_rect = pygame.Rect(ar.x + 4, ar.y + 6, 12, 14)
            pygame.draw.rect(surface, self.indicator_color, ind_rect, border_radius=2)
            text_x = ar.x + 22

        label = font.render(self.text, True, Theme.TEXT_BRIGHT if self.selected else Theme.TEXT)
        surface.blit(label, (text_x, ar.y + 4))

    def handle_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.abs_rect.collidepoint(mx, my):
                if self.on_select:
                    self.on_select(UIEvent(self, self.data))
                return True
        return False


class TextInput(Widget):
    """Simple text input field."""

    def __init__(self, x: int, y: int, w: int, h: int = Theme.ITEM_HEIGHT,
                 text: str = "", on_change: Callable | None = None):
        super().__init__(x, y, w, h)
        self.text = text
        self.on_change = on_change
        self.cursor_pos = len(text)
        self._active = False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.visible:
            return
        ar = self.abs_rect
        bg = Theme.BG_INPUT
        border = Theme.BORDER_FOCUS if self._active else Theme.BORDER
        pygame.draw.rect(surface, bg, ar, border_radius=3)
        pygame.draw.rect(surface, border, ar, 1, border_radius=3)

        # Text
        label = font.render(self.text, True, Theme.TEXT)
        surface.blit(label, (ar.x + 4, ar.y + 3))

        # Cursor
        if self._active:
            cursor_x = ar.x + 4 + font.size(self.text[:self.cursor_pos])[0]
            pygame.draw.line(surface, Theme.TEXT_BRIGHT,
                             (cursor_x, ar.y + 3), (cursor_x, ar.y + ar.h - 3), 1)

    def handle_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._active = self.abs_rect.collidepoint(mx, my)
            return self._active
        if not self._active:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                if self.cursor_pos > 0:
                    self.text = self.text[:self.cursor_pos - 1] + self.text[self.cursor_pos:]
                    self.cursor_pos -= 1
                    if self.on_change:
                        self.on_change(UIEvent(self, self.text))
                return True
            elif event.key == pygame.K_DELETE:
                if self.cursor_pos < len(self.text):
                    self.text = self.text[:self.cursor_pos] + self.text[self.cursor_pos + 1:]
                    if self.on_change:
                        self.on_change(UIEvent(self, self.text))
                return True
            elif event.key == pygame.K_LEFT:
                self.cursor_pos = max(0, self.cursor_pos - 1)
                return True
            elif event.key == pygame.K_RIGHT:
                self.cursor_pos = min(len(self.text), self.cursor_pos + 1)
                return True
            elif event.key == pygame.K_HOME:
                self.cursor_pos = 0
                return True
            elif event.key == pygame.K_END:
                self.cursor_pos = len(self.text)
                return True
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._active = False
                return True
            elif event.key == pygame.K_ESCAPE:
                self._active = False
                return True
            elif event.unicode and event.unicode.isprintable():
                self.text = self.text[:self.cursor_pos] + event.unicode + self.text[self.cursor_pos:]
                self.cursor_pos += 1
                if self.on_change:
                    self.on_change(UIEvent(self, self.text))
                return True
        return False


class NumberInput(Widget):
    """Numeric input with up/down buttons."""

    def __init__(self, x: int, y: int, w: int, h: int = Theme.ITEM_HEIGHT,
                 value: int = 0, min_val: int = 0, max_val: int = 9999,
                 on_change: Callable | None = None):
        super().__init__(x, y, w, h)
        self.value = value
        self.min_val = min_val
        self.max_val = max_val
        self.on_change = on_change
        self._text_input = TextInput(0, 0, w - 32, h, text=str(value))
        self._text_input.on_change = self._on_text_change

    def _on_text_change(self, evt: UIEvent) -> None:
        try:
            val = int(evt.data)
            val = max(self.min_val, min(self.max_val, val))
            self.value = val
            if self.on_change:
                self.on_change(UIEvent(self, self.value))
        except ValueError:
            pass

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.visible:
            return
        ar = self.abs_rect
        self._text_input.rect = pygame.Rect(ar.x, ar.y, ar.w - 32, ar.h)
        self._text_input.parent = None  # Direct position
        self._text_input.draw(surface, font)

        # Up/Down buttons
        btn_w = 16
        btn_x = ar.x + ar.w - 32
        # Up
        up_rect = pygame.Rect(btn_x, ar.y, btn_w, ar.h // 2)
        pygame.draw.rect(surface, Theme.BG_BUTTON, up_rect)
        pygame.draw.rect(surface, Theme.BORDER, up_rect, 1)
        # Down
        dn_rect = pygame.Rect(btn_x, ar.y + ar.h // 2, btn_w, ar.h // 2)
        pygame.draw.rect(surface, Theme.BG_BUTTON, dn_rect)
        pygame.draw.rect(surface, Theme.BORDER, dn_rect, 1)

        # Arrows
        cx = btn_x + btn_w // 2
        pygame.draw.polygon(surface, Theme.TEXT, [
            (cx, ar.y + 3), (cx - 4, ar.y + ar.h // 2 - 2), (cx + 4, ar.y + ar.h // 2 - 2)
        ])
        pygame.draw.polygon(surface, Theme.TEXT, [
            (cx, ar.y + ar.h - 3), (cx - 4, ar.y + ar.h // 2 + 2), (cx + 4, ar.y + ar.h // 2 + 2)
        ])

    def handle_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        if not self.visible or not self.enabled:
            return False
        ar = self.abs_rect
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            btn_x = ar.x + ar.w - 32
            btn_w = 16
            up_rect = pygame.Rect(btn_x, ar.y, btn_w, ar.h // 2)
            dn_rect = pygame.Rect(btn_x, ar.y + ar.h // 2, btn_w, ar.h // 2)
            if up_rect.collidepoint(mx, my):
                self.value = min(self.max_val, self.value + 1)
                self._text_input.text = str(self.value)
                if self.on_change:
                    self.on_change(UIEvent(self, self.value))
                return True
            if dn_rect.collidepoint(mx, my):
                self.value = max(self.min_val, self.value - 1)
                self._text_input.text = str(self.value)
                if self.on_change:
                    self.on_change(UIEvent(self, self.value))
                return True
        return self._text_input.handle_event(event, mx, my)


class Checkbox(Widget):
    """Boolean toggle checkbox."""

    def __init__(self, x: int, y: int, label: str = "", checked: bool = False,
                 on_change: Callable | None = None):
        super().__init__(x, y, 200, Theme.ITEM_HEIGHT)
        self.label = label
        self.checked = checked
        self.on_change = on_change

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.visible:
            return
        ar = self.abs_rect
        box = pygame.Rect(ar.x, ar.y + 4, 16, 16)
        pygame.draw.rect(surface, Theme.BG_INPUT, box, border_radius=2)
        pygame.draw.rect(surface, Theme.BORDER_LIGHT, box, 1, border_radius=2)
        if self.checked:
            pygame.draw.rect(surface, Theme.ACCENT, box.inflate(-4, -4), border_radius=1)
        lbl = font.render(self.label, True, Theme.TEXT)
        surface.blit(lbl, (ar.x + 22, ar.y + 4))

    def handle_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.abs_rect.collidepoint(mx, my):
                self.checked = not self.checked
                if self.on_change:
                    self.on_change(UIEvent(self, self.checked))
                return True
        return False


class DropdownSelect(Widget):
    """Dropdown selection widget."""

    def __init__(self, x: int, y: int, w: int, h: int = Theme.ITEM_HEIGHT,
                 options: list[str] | None = None, selected: int = 0,
                 on_change: Callable | None = None):
        super().__init__(x, y, w, h)
        self.options = options or []
        self.selected = selected
        self.on_change = on_change
        self._open = False

    @property
    def selected_text(self) -> str:
        if 0 <= self.selected < len(self.options):
            return self.options[self.selected]
        return ""

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.visible:
            return
        ar = self.abs_rect
        bg = Theme.BG_INPUT
        pygame.draw.rect(surface, bg, ar, border_radius=3)
        pygame.draw.rect(surface, Theme.BORDER_LIGHT, ar, 1, border_radius=3)

        lbl = font.render(self.selected_text, True, Theme.TEXT)
        surface.blit(lbl, (ar.x + 6, ar.y + 3))

        # Arrow
        ax = ar.x + ar.w - 14
        ay = ar.y + ar.h // 2
        pygame.draw.polygon(surface, Theme.TEXT_DIM, [
            (ax - 4, ay - 2), (ax + 4, ay - 2), (ax, ay + 3)
        ])

        # Dropdown list
        if self._open and self.options:
            list_h = len(self.options) * Theme.ITEM_HEIGHT
            list_rect = pygame.Rect(ar.x, ar.y + ar.h, ar.w, list_h)
            pygame.draw.rect(surface, Theme.BG_PANEL, list_rect)
            pygame.draw.rect(surface, Theme.BORDER_LIGHT, list_rect, 1)
            for i, opt in enumerate(self.options):
                item_rect = pygame.Rect(ar.x, ar.y + ar.h + i * Theme.ITEM_HEIGHT,
                                        ar.w, Theme.ITEM_HEIGHT)
                if i == self.selected:
                    pygame.draw.rect(surface, Theme.BG_SELECTED, item_rect)
                opt_lbl = font.render(opt, True, Theme.TEXT)
                surface.blit(opt_lbl, (item_rect.x + 6, item_rect.y + 3))

    def handle_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        if not self.visible or not self.enabled:
            return False
        ar = self.abs_rect
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if ar.collidepoint(mx, my):
                self._open = not self._open
                return True
            if self._open:
                for i in range(len(self.options)):
                    item_rect = pygame.Rect(ar.x, ar.y + ar.h + i * Theme.ITEM_HEIGHT,
                                            ar.w, Theme.ITEM_HEIGHT)
                    if item_rect.collidepoint(mx, my):
                        self.selected = i
                        self._open = False
                        if self.on_change:
                            self.on_change(UIEvent(self, i))
                        return True
                self._open = False
        return False


class ColorSwatch(Widget):
    """Small color display/picker."""

    def __init__(self, x: int, y: int, size: int = 20,
                 color: tuple[int, int, int] = (128, 128, 128),
                 on_click: Callable | None = None):
        super().__init__(x, y, size, size)
        self.color = color
        self.on_click = on_click
        self.selected = False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.visible:
            return
        ar = self.abs_rect
        pygame.draw.rect(surface, self.color, ar, border_radius=2)
        border_color = Theme.BORDER_FOCUS if self.selected else Theme.BORDER
        pygame.draw.rect(surface, border_color, ar, 2 if self.selected else 1, border_radius=2)

    def handle_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.abs_rect.collidepoint(mx, my):
                if self.on_click:
                    self.on_click(UIEvent(self))
                return True
        return False
