"""
统一 GUI 主题工具。

项目使用 tkinter/ttk，不引入第三方主题库。这里集中管理颜色、字体、
间距和常用控件样式，让各窗口保持一致的现代清爽视觉。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, font
from typing import Any, Optional


MODERN_LIGHT = {
    "background": "#F5F7FB",
    "surface": "#FFFFFF",
    "surface_alt": "#EEF3F8",
    "border": "#D8E0EA",
    "text": "#1F2937",
    "text_muted": "#64748B",
    "primary": "#2563EB",
    "primary_active": "#1D4ED8",
    "primary_soft": "#DBEAFE",
    "secondary": "#475569",
    "secondary_active": "#334155",
    "danger": "#DC2626",
    "danger_active": "#B91C1C",
    "danger_soft": "#FEE2E2",
    "success": "#16A34A",
    "success_soft": "#DCFCE7",
    "warning": "#D97706",
    "warning_soft": "#FEF3C7",
    "info": "#0284C7",
    "info_soft": "#E0F2FE",
    "disabled": "#CBD5E1",
    "selection": "#BFDBFE",
}

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
}

STATUS_TAGS = {
    "pending": ("等待", "status_pending"),
    "running": ("运行中", "status_running"),
    "completed": ("完成", "status_completed"),
    "failed": ("失败", "status_failed"),
    "cancelled": ("取消", "status_cancelled"),
    "scheduled": ("计划中", "status_scheduled"),
}


def _config_get(config: Any, key: str, default: Any = None) -> Any:
    if config is None:
        return default
    getter = getattr(config, "get", None)
    if callable(getter):
        return getter(key, default)
    if isinstance(config, dict):
        value: Any = config
        for part in key.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value
    return default


def normalize_theme_name(theme_name: Optional[str]) -> str:
    value = (theme_name or "modern_light").strip().lower()
    if value in {"default", "modern", "modern-light", "modern_light", "清爽", "现代清爽"}:
        return "modern_light"
    if value in {"system", "system_default", "系统默认"}:
        return "system"
    return "modern_light"


def apply_app_theme(widget: tk.Misc, config: Any = None) -> dict[str, str]:
    """应用全局 ttk 样式并返回当前调色盘。"""
    theme_name = normalize_theme_name(_config_get(config, "gui.theme", "modern_light"))
    palette = MODERN_LIGHT
    try:
        setattr(widget, "_app_theme_name", theme_name)
    except Exception:
        pass

    try:
        widget.configure(bg=palette["background"])
    except tk.TclError:
        pass

    _configure_fonts()

    style = ttk.Style(widget)
    if theme_name == "modern_light":
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

    _configure_base_styles(style, palette)
    _configure_button_styles(style, palette)
    _configure_treeview_styles(style, palette)
    _configure_feedback_styles(style, palette)
    return palette


def _configure_fonts() -> None:
    try:
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family="Microsoft YaHei UI", size=10)
        font.nametofont("TkTextFont").configure(family="Microsoft YaHei UI", size=10)
        font.nametofont("TkMenuFont").configure(family="Microsoft YaHei UI", size=10)
        font.nametofont("TkHeadingFont").configure(family="Microsoft YaHei UI", size=10, weight="bold")
    except tk.TclError:
        # 字体名在不同平台可能不存在；Tk 会自动回退。
        pass


def _configure_base_styles(style: ttk.Style, palette: dict[str, str]) -> None:
    style.configure(".", background=palette["background"], foreground=palette["text"])
    style.configure("App.TFrame", background=palette["background"])
    style.configure("Surface.TFrame", background=palette["surface"])
    style.configure("Card.TFrame", background=palette["surface"], relief="flat")
    style.configure("Toolbar.TFrame", background=palette["background"])
    style.configure("Status.TFrame", background=palette["surface_alt"])

    style.configure("App.TLabel", background=palette["background"], foreground=palette["text"])
    style.configure("Surface.TLabel", background=palette["surface"], foreground=palette["text"])
    style.configure("Muted.TLabel", background=palette["background"], foreground=palette["text_muted"])
    style.configure("SurfaceMuted.TLabel", background=palette["surface"], foreground=palette["text_muted"])
    style.configure("StatusMuted.TLabel", background=palette["surface_alt"], foreground=palette["text_muted"])
    style.configure("Title.TLabel", background=palette["background"], foreground=palette["text"], font=("Microsoft YaHei UI", 16, "bold"))
    style.configure("Subtitle.TLabel", background=palette["background"], foreground=palette["text_muted"])
    style.configure("CardTitle.TLabel", background=palette["surface"], foreground=palette["text"], font=("Microsoft YaHei UI", 11, "bold"))

    style.configure("App.TLabelframe", background=palette["surface"], bordercolor=palette["border"], relief="solid")
    style.configure("App.TLabelframe.Label", background=palette["surface"], foreground=palette["text"], font=("Microsoft YaHei UI", 10, "bold"))
    style.configure("TLabelframe", background=palette["surface"], bordercolor=palette["border"])
    style.configure("TLabelframe.Label", background=palette["surface"], foreground=palette["text"])

    style.configure("TEntry", fieldbackground=palette["surface"], bordercolor=palette["border"], lightcolor=palette["border"], darkcolor=palette["border"], padding=4)
    style.configure("TSpinbox", fieldbackground=palette["surface"], bordercolor=palette["border"], padding=4)
    style.configure("TCombobox", fieldbackground=palette["surface"], bordercolor=palette["border"], padding=4)
    style.configure("TCheckbutton", background=palette["surface"], foreground=palette["text"])
    style.configure("TRadiobutton", background=palette["surface"], foreground=palette["text"])
    style.configure("Horizontal.TSeparator", background=palette["border"])


def _configure_button_styles(style: ttk.Style, palette: dict[str, str]) -> None:
    base_padding = (12, 7)
    for style_name, bg, active_bg, fg in [
        ("Primary.TButton", palette["primary"], palette["primary_active"], "#FFFFFF"),
        ("Secondary.TButton", palette["surface"], palette["surface_alt"], palette["text"]),
        ("Danger.TButton", palette["danger"], palette["danger_active"], "#FFFFFF"),
        ("Ghost.TButton", palette["background"], palette["surface_alt"], palette["secondary"]),
    ]:
        style.configure(style_name, padding=base_padding, background=bg, foreground=fg, bordercolor=palette["border"], focusthickness=1, focuscolor=palette["selection"])
        style.map(
            style_name,
            background=[("disabled", palette["disabled"]), ("pressed", active_bg), ("active", active_bg)],
            foreground=[("disabled", palette["text_muted"])],
            bordercolor=[("focus", palette["primary"])],
        )

    style.configure("TButton", padding=base_padding)


def _configure_treeview_styles(style: ttk.Style, palette: dict[str, str]) -> None:
    style.configure(
        "App.Treeview",
        background=palette["surface"],
        fieldbackground=palette["surface"],
        foreground=palette["text"],
        bordercolor=palette["border"],
        rowheight=30,
        font=("Microsoft YaHei UI", 10),
    )
    style.configure(
        "App.Treeview.Heading",
        background=palette["surface_alt"],
        foreground=palette["text"],
        relief="flat",
        font=("Microsoft YaHei UI", 10, "bold"),
    )
    style.map("App.Treeview", background=[("selected", palette["selection"])], foreground=[("selected", palette["text"])])


def _configure_feedback_styles(style: ttk.Style, palette: dict[str, str]) -> None:
    style.configure("App.Horizontal.TProgressbar", troughcolor=palette["surface_alt"], background=palette["primary"], bordercolor=palette["border"], lightcolor=palette["primary"], darkcolor=palette["primary"])
    for name, color, bg in [
        ("Success", palette["success"], palette["success_soft"]),
        ("Info", palette["info"], palette["info_soft"]),
        ("Warning", palette["warning"], palette["warning_soft"]),
        ("Danger", palette["danger"], palette["danger_soft"]),
    ]:
        style.configure(f"{name}.TLabel", background=bg, foreground=color, padding=(8, 3), font=("Microsoft YaHei UI", 9, "bold"))


def style_button(button: ttk.Button, variant: str = "secondary") -> ttk.Button:
    style_name = {
        "primary": "Primary.TButton",
        "secondary": "Secondary.TButton",
        "danger": "Danger.TButton",
        "ghost": "Ghost.TButton",
    }.get(variant, "Secondary.TButton")
    button.configure(style=style_name)
    return button


def style_window(window: tk.Misc, config: Any = None) -> dict[str, str]:
    if config is None:
        parent = getattr(window, "master", None)
        inherited_theme = getattr(parent, "_app_theme_name", None)
        if inherited_theme:
            config = {"gui": {"theme": inherited_theme}}
    palette = apply_app_theme(window, config)
    try:
        window.configure(bg=palette["background"])
    except tk.TclError:
        pass
    return palette


def center_window(
    window: tk.Toplevel | tk.Tk,
    parent: Optional[tk.Misc] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> None:
    """居中窗口；传入 width/height 时同时设置尺寸。"""
    window.update_idletasks()
    if width is None:
        width = max(window.winfo_width(), window.winfo_reqwidth())
    if height is None:
        height = max(window.winfo_height(), window.winfo_reqheight())

    if parent is not None:
        x = parent.winfo_rootx() + max((parent.winfo_width() - width) // 2, 24)
        y = parent.winfo_rooty() + max((parent.winfo_height() - height) // 2, 24)
    else:
        x = (window.winfo_screenwidth() - width) // 2
        y = (window.winfo_screenheight() - height) // 2

    window.geometry(f"{width}x{height}+{x}+{y}")


def configure_treeview_tags(tree: ttk.Treeview) -> None:
    palette = MODERN_LIGHT
    tree.tag_configure("status_pending", background=palette["surface"], foreground=palette["secondary"])
    tree.tag_configure("status_running", background=palette["info_soft"], foreground=palette["info"])
    tree.tag_configure("status_completed", background=palette["success_soft"], foreground=palette["success"])
    tree.tag_configure("status_failed", background=palette["danger_soft"], foreground=palette["danger"])
    tree.tag_configure("status_cancelled", background=palette["surface_alt"], foreground=palette["text_muted"])
    tree.tag_configure("status_scheduled", background=palette["warning_soft"], foreground=palette["warning"])


def status_tag(status: Any) -> str:
    value = getattr(status, "value", status)
    return STATUS_TAGS.get(str(value), ("未知", "status_pending"))[1]


def status_text(status: Any) -> str:
    value = getattr(status, "value", status)
    return STATUS_TAGS.get(str(value), ("未知", "status_pending"))[0]


def status_label_style(status: Any) -> str:
    value = getattr(status, "value", status)
    if value == "completed":
        return "Success.TLabel"
    if value == "running":
        return "Info.TLabel"
    if value in {"failed", "cancelled"}:
        return "Danger.TLabel"
    if value == "scheduled":
        return "Warning.TLabel"
    return "SurfaceMuted.TLabel"
