"""PyEGA Trek — NiceGUI frontend for the EGATrek clone."""

from __future__ import annotations

from nicegui import ui
import game as G

# ---------------------------------------------------------------------------
# Module-level game state (single user / dev mode)
# ---------------------------------------------------------------------------

_state: G.GameState | None = None


def get_state() -> G.GameState | None:
    return _state


def new_game(klingons: int = 15, starbases: int = 4, stardates: int = 25) -> None:
    global _state
    _state = G.GameState(num_klingons=klingons, num_starbases=starbases, stardates=stardates)


# ---------------------------------------------------------------------------
# Visual config
# ---------------------------------------------------------------------------

CELL_CLASSES: dict[str, str] = {
    "ship":     "text-green-400 bg-green-950 font-bold",
    "klingon":  "text-red-400 bg-red-950 font-bold",
    "starbase": "text-cyan-400 bg-cyan-950 font-bold",
    "star":     "text-yellow-400",
    "empty":    "text-gray-700",
}

CONDITION_CLASSES: dict[str, str] = {
    "GREEN":  "text-green-400",
    "YELLOW": "text-yellow-400",
    "RED":    "text-red-500",
    "DOCKED": "text-cyan-400",
}

MSG_CLASSES: dict[str, str] = {
    "error":   "text-red-400",
    "success": "text-cyan-300",
    "warning": "text-yellow-400",
    "normal":  "text-green-300",
}

# Global log element reference (populated when UI is built)
_log: ui.log | None = None


# ---------------------------------------------------------------------------
# Refreshable display components
# ---------------------------------------------------------------------------


@ui.refreshable
def sector_grid() -> None:
    g = get_state()
    if g is None:
        return

    display = g.get_sector_display()

    with ui.card().classes("bg-black border border-gray-700 p-3"):
        with ui.row().classes("justify-between items-center mb-2 font-mono"):
            ui.label(
                f"QUADRANT ({g.q_pos.row + 1},{g.q_pos.col + 1})"
            ).classes("text-green-300 text-sm font-bold")
            ui.label(
                f"SECTOR ({g.s_pos.row + 1},{g.s_pos.col + 1})"
            ).classes("text-green-600 text-sm")

        # Column headers
        with ui.row().classes("gap-0 mb-0.5 ml-7"):
            for c in range(8):
                ui.label(str(c + 1)).classes("text-gray-600 font-mono text-xs w-8 text-center")

        for r in range(8):
            with ui.row().classes("gap-0 items-center"):
                ui.label(str(r + 1)).classes("text-gray-600 font-mono text-xs w-6 text-right mr-1")
                for c in range(8):
                    entry = display.get((r, c))
                    if entry:
                        sym, kind = entry
                        cls = CELL_CLASSES.get(kind, CELL_CLASSES["empty"])
                    else:
                        sym, cls = "·", CELL_CLASSES["empty"]

                    ui.label(sym).classes(
                        f"{cls} font-mono text-lg w-8 h-8 flex items-center "
                        "justify-center border border-gray-900 hover:bg-gray-800 cursor-default"
                    )

        # Legend
        with ui.row().classes("mt-2 gap-3 font-mono text-xs"):
            for sym, kind, label in [
                ("E", "ship", "Enterprise"),
                ("K", "klingon", "Klingon"),
                ("B", "starbase", "Starbase"),
                ("*", "star", "Star"),
            ]:
                cls = CELL_CLASSES[kind].split()[0]  # just the text colour
                with ui.row().classes("items-center gap-1"):
                    ui.label(sym).classes(f"{cls} font-bold")
                    ui.label(label).classes("text-gray-500")


@ui.refreshable
def status_panel() -> None:
    g = get_state()
    if g is None:
        return

    cond = g.condition
    cond_cls = CONDITION_CLASSES.get(cond, "text-green-400")

    with ui.card().classes("bg-gray-900 border border-gray-700 p-3 font-mono w-full"):
        ui.label("SHIP STATUS").classes("text-green-400 font-bold text-sm mb-2")

        def row(label: str, value: str, vcls: str = "text-green-300") -> None:
            with ui.row().classes("justify-between w-full mb-1"):
                ui.label(label).classes("text-gray-500 text-xs")
                ui.label(value).classes(f"{vcls} text-xs font-bold")

        row("Condition", cond, cond_cls)
        row("Stardate", f"{g.stardate:.1f}")

        ui.separator().classes("my-1 border-gray-700")

        # Energy with bar
        energy_pct = max(0.0, min(1.0, g.energy / G.INITIAL_ENERGY))
        e_color = "text-red-400" if energy_pct < 0.2 else "text-yellow-400" if energy_pct < 0.5 else "text-green-300"
        row("Energy", str(g.energy), e_color)
        with ui.row().classes("w-full h-2 bg-gray-800 rounded mb-1"):
            bar_color = "bg-red-500" if energy_pct < 0.2 else "bg-yellow-500" if energy_pct < 0.5 else "bg-green-500"
            ui.element("div").classes(f"{bar_color} h-2 rounded").style(f"width:{energy_pct * 100:.0f}%")

        # Shields with bar
        shield_pct = max(0.0, min(1.0, g.shields / G.MAX_SHIELDS))
        row("Shields", str(g.shields), "text-blue-300")
        with ui.row().classes("w-full h-2 bg-gray-800 rounded mb-1"):
            ui.element("div").classes("bg-blue-500 h-2 rounded").style(f"width:{shield_pct * 100:.0f}%")

        row("Torpedoes", str(g.torpedoes), "text-orange-300")

        ui.separator().classes("my-1 border-gray-700")

        row("Klingons left", str(g.galaxy.total_klingons), "text-red-400")
        row("Starbases left", str(g.galaxy.total_starbases), "text-cyan-400")
        row("Quadrant", f"({g.q_pos.row + 1},{g.q_pos.col + 1})")

        ui.separator().classes("my-1 border-gray-700")

        # Damage summary
        any_damage = any(lvl > 0 for _, _, lvl in g.damage.all_systems())
        if any_damage:
            ui.label("DAMAGE:").classes("text-red-400 text-xs font-bold mt-1 mb-1")
            for _, name, lvl in g.damage.all_systems():
                if lvl > 0:
                    ui.label(f"  {name}: {lvl} turns").classes("text-red-300 text-xs")
        else:
            ui.label("All systems nominal").classes("text-green-600 text-xs mt-1")


@ui.refreshable
def galaxy_map() -> None:
    g = get_state()
    if g is None:
        return

    data = g.get_galaxy_display()

    with ui.card().classes("bg-black border border-gray-700 p-2 font-mono"):
        ui.label("GALAXY MAP").classes("text-green-400 text-xs font-bold mb-1")
        ui.label("K=Klingons B=Starbases S=Stars").classes("text-gray-600 text-xs mb-1")

        # Column headers
        with ui.row().classes("gap-0 mb-0.5 ml-4"):
            for c in range(8):
                ui.label(str(c + 1)).classes("text-gray-700 text-xs text-center").style("width:32px")

        for r in range(8):
            with ui.row().classes("gap-0 items-center"):
                ui.label(str(r + 1)).classes("text-gray-700 text-xs w-4 text-right mr-0.5")
                for c in range(8):
                    code, is_current, scanned = data[r][c]
                    if is_current:
                        cls = "text-green-400 border border-green-500"
                    elif not scanned:
                        cls = "text-gray-800 border border-gray-900"
                    else:
                        k = int(code[0]) if code != "???" else 0
                        b = code[1] if code != "???" else "0"
                        if k > 0:
                            cls = "text-red-400 border border-gray-800"
                        elif b != "0":
                            cls = "text-cyan-400 border border-gray-800"
                        else:
                            cls = "text-gray-500 border border-gray-800"

                    ui.label(code).classes(
                        f"{cls} text-center font-mono p-0.5"
                    ).style("width:32px; font-size:9px;")


# ---------------------------------------------------------------------------
# Message log
# ---------------------------------------------------------------------------


def push_messages(msgs: list[str]) -> None:
    global _log
    if _log is None:
        return
    for msg in msgs:
        _log.push(msg)


def _classify_msg(msg: str) -> str:
    lower = msg.lower()
    if any(w in lower for w in ["destroyed!", "lost", "depleted", "damaged!", "damaged ("]):
        return MSG_CLASSES["error"]
    if any(w in lower for w in ["docked", "replenished", "repaired", "accomplished"]):
        return MSG_CLASSES["success"]
    if any(w in lower for w in ["warning", "alert", "klingon fires", "fires"]):
        return MSG_CLASSES["warning"]
    return MSG_CLASSES["normal"]


# ---------------------------------------------------------------------------
# Command handling
# ---------------------------------------------------------------------------


def handle_command(input_el: ui.input) -> None:
    global _log
    raw = input_el.value
    if not raw or not raw.strip():
        return
    input_el.set_value("")

    g = get_state()
    if g is None:
        return

    if _log:
        _log.push(f"> {raw}")

    msgs = G.parse_and_execute(g, raw)
    push_messages(msgs)

    sector_grid.refresh()
    status_panel.refresh()
    galaxy_map.refresh()

    if g.game_over:
        show_game_over_dialog(g)


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------


def show_help_dialog() -> None:
    with ui.dialog() as dlg, ui.card().classes("bg-gray-900 font-mono max-w-xl"):
        ui.label("COMMAND REFERENCE").classes("text-green-400 font-bold mb-3")
        rows = [
            ("warp QR QC", "Warp to quadrant row/col (1–8)"),
            ("mov  SR SC", "Impulse move to sector row/col (1–8)"),
            ("pha  POWER", "Fire phasers with POWER energy units"),
            ("tor  TR TC", "Fire torpedo at sector row/col (1–8)"),
            ("she  LEVEL", "Set shield energy level"),
            ("lrs",        "Long range scan (3×3 quadrant view)"),
            ("dam",        "Damage report"),
            ("dock",       "Dock with adjacent starbase"),
            ("status",     "Full status report"),
            ("help",       "This message"),
            ("quit",       "Surrender"),
        ]
        with ui.grid(columns=2).classes("gap-x-4 gap-y-1 w-full"):
            for cmd, desc in rows:
                ui.label(cmd).classes("text-yellow-400 text-sm")
                ui.label(desc).classes("text-gray-300 text-sm")
        ui.label("Abbreviations: w m p t s l d  work for most commands").classes(
            "text-gray-500 text-xs mt-3"
        )
        ui.button("Close", on_click=dlg.close).classes("mt-3 bg-gray-700 text-gray-200")
    dlg.open()


def show_game_over_dialog(g: G.GameState) -> None:
    with ui.dialog() as dlg, ui.card().classes("bg-gray-950 font-mono text-center p-8 min-w-80"):
        if g.won:
            ui.label("MISSION ACCOMPLISHED").classes("text-green-400 text-2xl font-bold")
            ui.label("All Klingon vessels destroyed!").classes("text-green-300 mt-2 text-sm")
        elif g.stardate <= 0:
            ui.label("MISSION FAILED").classes("text-red-400 text-2xl font-bold")
            ui.label("Time has run out. The Federation falls.").classes("text-red-300 mt-2 text-sm")
        else:
            ui.label("SHIP DESTROYED").classes("text-red-400 text-2xl font-bold")
            ui.label("The Enterprise has been lost.").classes("text-red-300 mt-2 text-sm")

        remaining = g.galaxy.total_klingons
        ui.label(f"Klingons remaining: {remaining}").classes("text-gray-400 mt-2 text-sm")

        def restart() -> None:
            dlg.close()
            ui.navigate.reload()

        ui.button("NEW GAME", on_click=restart).classes("mt-6 bg-green-700 text-black font-bold px-6")
    dlg.open()


def show_new_game_dialog(on_start) -> None:
    with ui.dialog() as dlg, ui.card().classes("bg-gray-950 font-mono p-6 min-w-96"):
        ui.label("** STAR TREK **").classes("text-green-400 font-bold text-2xl text-center mb-1")
        ui.label("A Python / NiceGUI homage to EGATrek").classes("text-gray-500 text-xs text-center mb-4")

        difficulty = ui.select(
            label="Difficulty",
            options={
                "easy":   "Cadet  — 10 Klingons, 30 stardates",
                "normal": "Captain — 15 Klingons, 25 stardates",
                "hard":   "Admiral — 20 Klingons, 20 stardates",
            },
            value="normal",
        ).classes("w-full")

        def start() -> None:
            params = {"easy": (10, 30), "normal": (15, 25), "hard": (20, 20)}
            klingons, stardates = params[difficulty.value]
            dlg.close()
            on_start(klingons, stardates)

        ui.button("BEGIN MISSION", on_click=start).classes(
            "w-full mt-4 bg-green-700 text-black font-bold"
        )
    dlg.open()


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------


@ui.page("/")
def index() -> None:
    global _log

    ui.dark_mode().enable()
    ui.query("body").classes("bg-black")

    def start_game(klingons: int, stardates: int) -> None:
        new_game(klingons=klingons, starbases=4, stardates=stardates)
        # Push initial messages to log
        g = get_state()
        if g and _log:
            for msg in g.messages:
                _log.push(msg)
        sector_grid.refresh()
        status_panel.refresh()
        galaxy_map.refresh()

    # ---- Header ----
    with ui.header().classes("bg-gray-950 border-b border-gray-800 items-center justify-between px-4 py-2"):
        ui.label("** STAR TREK **").classes("text-green-400 font-mono font-bold text-xl")
        ui.label("A NiceGUI / EGATrek Clone").classes("text-gray-600 font-mono text-xs")
        ui.button("New Game", on_click=lambda: show_new_game_dialog(start_game)).classes(
            "bg-gray-800 text-green-400 font-mono text-xs px-3"
        )

    # ---- Main body ----
    with ui.row().classes("w-full gap-4 p-4 flex-nowrap items-start"):

        # Left column: sector grid + galaxy map
        with ui.column().classes("gap-4 flex-shrink-0"):
            sector_grid()
            galaxy_map()

        # Right column: status + message log + command input
        with ui.column().classes("flex-grow gap-3 min-w-0"):
            status_panel()

            # Message log
            with ui.card().classes("bg-black border border-gray-700 w-full p-0"):
                ui.label("MESSAGE LOG").classes("text-green-400 font-mono text-xs font-bold px-3 pt-2")
                _log = ui.log(max_lines=200).classes(
                    "w-full bg-black text-green-300 font-mono text-xs border-0"
                ).style("height: 280px;")

            # Command input
            with ui.card().classes("bg-gray-950 border border-gray-700 w-full p-3"):
                ui.label("COMMAND").classes("text-green-400 font-mono text-xs font-bold mb-2")
                with ui.row().classes("w-full gap-2 items-center"):
                    cmd_input = (
                        ui.input(placeholder="e.g.  warp 3 4  |  pha 500  |  tor 2 6  |  lrs")
                        .classes("flex-grow font-mono text-green-300 bg-black")
                        .props("dark dense standout outlined")
                    )
                    cmd_input.on("keydown.enter", lambda: handle_command(cmd_input))
                    ui.button("SEND", on_click=lambda: handle_command(cmd_input)).classes(
                        "bg-green-800 text-green-200 font-mono text-sm px-4"
                    )
                    ui.button("HELP", on_click=show_help_dialog).classes(
                        "bg-gray-700 text-gray-300 font-mono text-sm px-3"
                    )

    # Auto-show new game dialog on first visit
    show_new_game_dialog(start_game)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ in ("__main__", "__mp_main__"):
    ui.run(
        title="Star Trek",
        dark=True,
        reload=False,
        port=8080,
        favicon="🚀",
    )
