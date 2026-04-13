"""
Jo — DESIGN.md System.

Tools for working with DESIGN.md files - design system documents
that AI agents read to generate consistent UI.
Inspired by awesome-design-md.
"""

from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class DesignToken:
    """A design token extracted from a DESIGN.md file."""

    name: str
    value: str
    role: str  # background, text, accent, border, etc.
    category: str  # color, typography, spacing, etc.


@dataclass
class DesignSystem:
    """A complete design system from a DESIGN.md file."""

    name: str
    source: str  # URL or file path
    theme: str  # dark, light, etc.
    colors: List[DesignToken] = field(default_factory=list)
    typography: List[DesignToken] = field(default_factory=list)
    components: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    spacing: List[DesignToken] = field(default_factory=list)
    shadows: List[DesignToken] = field(default_factory=list)


class DesignSystemRegistry:
    """Registry for DESIGN.md design systems."""

    def __init__(self, drive_root: pathlib.Path):
        self.drive_root = drive_root
        self.systems: Dict[str, DesignSystem] = {}
        self.registry_file = drive_root / "logs" / "design_systems.json"
        self.designs_dir = drive_root / "knowledge" / "designs"

        # Load built-in design systems
        self._load_builtin_systems()
        self._load_registry()

    def _load_builtin_systems(self) -> None:
        """Load built-in design systems from the awesome-design-md collection."""
        # Common design systems stored as JSON
        builtin = {
            "vercel": {
                "name": "Vercel",
                "theme": "dark",
                "colors": {
                    "background": "#000000",
                    "foreground": "#ffffff",
                    "accent": "#000000",
                    "muted": "#111111",
                    "border": "#333333",
                },
                "typography": {
                    "font": "Geist, sans-serif",
                    "mono": "Geist Mono, monospace",
                },
            },
            "linear": {
                "name": "Linear",
                "theme": "dark",
                "colors": {
                    "background": "#101113",
                    "foreground": "#EDEDEF",
                    "accent": "#5E6AD2",
                    "muted": "#1A1A1D",
                    "border": "#2E2E32",
                },
                "typography": {
                    "font": "Inter, sans-serif",
                    "mono": "JetBrains Mono, monospace",
                },
            },
            "cursor": {
                "name": "Cursor",
                "theme": "dark",
                "colors": {
                    "background": "#0A0A0A",
                    "foreground": "#EDEDEF",
                    "accent": "#FF6B6B",
                    "muted": "#1A1A1A",
                    "border": "#333333",
                },
                "typography": {
                    "font": "Inter, sans-serif",
                    "mono": "JetBrains Mono, monospace",
                },
            },
            "raycast": {
                "name": "Raycast",
                "theme": "dark",
                "colors": {
                    "background": "#1A1A1A",
                    "foreground": "#FFFFFF",
                    "accent": "#FF6363",
                    "muted": "#2A2A2A",
                    "border": "#333333",
                },
                "typography": {
                    "font": "Inter, sans-serif",
                    "mono": "JetBrains Mono, monospace",
                },
            },
            "supabase": {
                "name": "Supabase",
                "theme": "dark",
                "colors": {
                    "background": "#0A0A0A",
                    "foreground": "#FFFFFF",
                    "accent": "#24B16A",
                    "muted": "#1A1A1A",
                    "border": "#262626",
                },
                "typography": {
                    "font": "Inter, sans-serif",
                    "mono": "JetBrains Mono, monospace",
                },
            },
            "stripe": {
                "name": "Stripe",
                "theme": "light",
                "colors": {
                    "background": "#FFFFFF",
                    "foreground": "#1A1A1A",
                    "accent": "#635BFF",
                    "muted": "#F7F9FC",
                    "border": "#E6EBF1",
                },
                "typography": {
                    "font": "Stripe, sans-serif",
                    "mono": "Stripe Mono, monospace",
                },
            },
        }

        for key, data in builtin.items():
            colors = [DesignToken(name=k, value=v, role=k, category="color") for k, v in data.get("colors", {}).items()]

            fonts = data.get("typography", {})
            typography = [DesignToken(name=k, value=v, role=k, category="typography") for k, v in fonts.items()]

            self.systems[key] = DesignSystem(
                name=data["name"],
                source=f"builtin:{key}",
                theme=data["theme"],
                colors=colors,
                typography=typography,
            )

    def _load_registry(self) -> None:
        """Load custom design systems from registry file."""
        if not self.registry_file.exists():
            return

        try:
            data = json.loads(self.registry_file.read_text())
            for key, sys_data in data.items():
                self.systems[key] = DesignSystem(
                    name=sys_data["name"],
                    source=sys_data.get("source", ""),
                    theme=sys_data.get("theme", "dark"),
                    colors=[
                        DesignToken(
                            name=c["name"],
                            value=c["value"],
                            role=c.get("role", ""),
                            category=c.get("category", "color"),
                        )
                        for c in sys_data.get("colors", [])
                    ],
                    typography=[
                        DesignToken(
                            name=t["name"],
                            value=t["value"],
                            role=t.get("role", ""),
                            category=t.get("category", "typography"),
                        )
                        for t in sys_data.get("typography", [])
                    ],
                )
        except Exception as e:
            log.warning(f"Failed to load design system registry: {e}")

    def register_system(self, key: str, system: DesignSystem) -> None:
        """Register a design system."""
        self.systems[key] = system
        self._save_registry()

    def _save_registry(self) -> None:
        """Save design system registry."""
        data = {}
        for key, sys in self.systems.items():
            data[key] = {
                "name": sys.name,
                "source": sys.source,
                "theme": sys.theme,
                "colors": [
                    {"name": c.name, "value": c.value, "role": c.role, "category": c.category} for c in sys.colors
                ],
                "typography": [
                    {"name": t.name, "value": t.value, "role": t.role, "category": t.category} for t in sys.typography
                ],
            }

        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self.registry_file.write_text(json.dumps(data, indent=2))

    def get_system(self, key: str) -> Optional[DesignSystem]:
        """Get a design system by key."""
        return self.systems.get(key.lower())

    def list_systems(self) -> List[str]:
        """List available design system keys."""
        return list(self.systems.keys())

    def get_css_variables(self, key: str) -> Optional[str]:
        """Get CSS variables for a design system."""
        system = self.get_system(key)
        if not system:
            return None

        lines = [f"/* Design System: {system.name} */", ":root {"]

        # Colors
        for color in system.colors:
            lines.append(f"  --{color.name}: {color.value};")

        # Typography
        for typo in system.typography:
            lines.append(f"  --font-{typo.name}: {typo.value};")

        lines.append("}")

        return "\n".join(lines)

    def generate_component_prompt(
        self,
        system_key: str,
        component: str,
    ) -> Optional[str]:
        """Generate a prompt for creating a component in a design system style."""
        system = self.get_system(system_key)
        if not system:
            return None

        # Get accent color
        accent = None
        for color in system.colors:
            if color.role == "accent":
                accent = color.value
                break

        if not accent and system.colors:
            accent = system.colors[0].value

        # Get font
        font = "sans-serif"
        for typo in system.typography:
            if typo.role == "font":
                font = typo.value
                break

        prompt = f"""Create a {component} component that matches the {system.name} design system.

## Design System: {system.name} (Theme: {system.theme})

### Color Palette
"""

        for color in system.colors:
            prompt += f"- {color.role}: {color.value}\n"

        prompt += f"""
### Typography
- Font: {font}

### Style Guidelines
- Use the accent color ({accent}) for primary actions
- Follow the {system.theme} theme aesthetic
- Keep components minimal and focused

### CSS Variables Available
{self.get_css_variables(system_key)}

Generate the component with inline styles matching this design system."""
        return prompt


# Singleton
_registry: Optional[DesignSystemRegistry] = None


def get_design_registry(drive_root: pathlib.Path) -> DesignSystemRegistry:
    """Get or create the design system registry."""
    global _registry
    if _registry is None:
        _registry = DesignSystemRegistry(drive_root)
    return _registry
