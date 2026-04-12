"""PyEGA Trek — NiceGUI frontend for the EGATrek clone."""

from __future__ import annotations

import asyncio

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

CONDITION_BG: dict[str, str] = {
    "GREEN":  "#14532d",
    "YELLOW": "#713f12",
    "RED":    "#7f1d1d",
    "DOCKED": "#164e63",
}
CONDITION_FG: dict[str, str] = {
    "GREEN":  "#4ade80",
    "YELLOW": "#facc15",
    "RED":    "#f87171",
    "DOCKED": "#22d3ee",
}

MSG_CLASSES: dict[str, str] = {
    "error":   "text-red-400",
    "success": "text-cyan-300",
    "warning": "text-yellow-400",
    "normal":  "text-green-300",
}

# Layout constants (keep in sync with the CSS calc expressions in index())
_TITLE_H  = "36px"
_PANELS_H = "36vh"
_CMD_H    = "56px"
_LOG_H    = f"calc(100vh - {_TITLE_H} - {_PANELS_H} - {_CMD_H})"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msg_class(msg: str) -> str:
    lower = msg.lower()
    if any(w in lower for w in ["destroyed!", "lost", "depleted", "damaged!", "damaged ("]):
        return MSG_CLASSES["error"]
    if any(w in lower for w in ["docked", "replenished", "repaired", "accomplished"]):
        return MSG_CLASSES["success"]
    if any(w in lower for w in ["warning", "alert", "klingon", "fires"]):
        return MSG_CLASSES["warning"]
    return MSG_CLASSES["normal"]


def _panel(width: str, border_right: bool = True) -> ui.element:
    border = "border-right:1px solid #1f2937;" if border_right else ""
    return ui.element("div").style(
        f"width:{width}; height:100%; overflow:hidden; {border}"
    )


# ---------------------------------------------------------------------------
# Sector view  (top-left, 25%)
# ---------------------------------------------------------------------------

@ui.refreshable
def sector_grid() -> None:
    g = get_state()

    # Base font scales with viewport — all child sizes use em
    with ui.element("div").style(
        "background:black; padding:0.4em 0.6em; width:100%; height:100%; "
        "overflow:hidden; box-sizing:border-box; font-family:monospace; "
        "display:flex; flex-direction:column; "
        "font-size:clamp(10px, 2.2vmin, 36px);"
    ):
        if g is None:
            return

        display = g.get_sector_display()

        # Quadrant / sector coords
        with ui.element("div").style(
            "display:flex; justify-content:space-between; margin-bottom:0.3em; flex-shrink:0;"
        ):
            ui.label(f"QUAD ({g.q_pos.row + 1},{g.q_pos.col + 1})").style(
                "color:#86efac; font-size:0.85em; font-weight:bold;"
            )
            ui.label(f"SEC ({g.s_pos.row + 1},{g.s_pos.col + 1})").style(
                "color:#4ade80; font-size:0.75em;"
            )

        # Column headers
        with ui.element("div").style(
            "display:flex; margin-left:1.4em; margin-bottom:0.1em; flex-shrink:0;"
        ):
            for c in range(8):
                ui.label(str(c + 1)).style(
                    "flex:1; text-align:center; color:#374151; font-size:0.65em;"
                )

        # Grid rows — fill remaining height
        with ui.element("div").style(
            "display:flex; flex-direction:column; flex:1; min-height:0;"
        ):
            for r in range(8):
                with ui.element("div").style("display:flex; align-items:stretch; flex:1;"):
                    ui.label(str(r + 1)).style(
                        "width:1.4em; text-align:right; padding-right:0.2em; "
                        "color:#374151; font-size:0.65em; flex-shrink:0; "
                        "display:flex; align-items:center; justify-content:flex-end;"
                    )
                    for c in range(8):
                        entry = display.get((r, c))
                        sym, cls = ("·", CELL_CLASSES["empty"]) if not entry else entry
                        if entry:
                            cls = CELL_CLASSES.get(entry[1], CELL_CLASSES["empty"])
                        ui.label(sym).classes(f"{cls} font-mono").style(
                            "flex:1; display:flex; align-items:center; "
                            "justify-content:center; border:1px solid #0a0a0a; font-size:1em;"
                        )


# ---------------------------------------------------------------------------
# Status panel  (25%)
# ---------------------------------------------------------------------------

@ui.refreshable
def status_panel() -> None:
    g = get_state()

    with ui.element("div").style(
        "background:#0f172a; padding:8px; width:100%; height:100%; "
        "overflow:hidden; box-sizing:border-box; font-family:monospace;"
    ):
        if g is None:
            return

        cond = g.condition
        fg   = CONDITION_FG.get(cond, "#4ade80")
        bg   = CONDITION_BG.get(cond, "#14532d")

        # Alert badge — ui.label renders actual text, ui.element().text does not
        ui.label(f"◉  {cond}").style(
            f"background:{bg}; color:{fg}; text-align:center; font-weight:bold; "
            f"font-size:12px; padding:3px 6px; border-radius:3px; margin-bottom:6px; "
            f"font-family:monospace; width:100%; box-sizing:border-box;"
        )

        def stat(label: str, value: str, color: str = "#86efac") -> None:
            with ui.element("div").style(
                "display:flex; justify-content:space-between; margin-bottom:3px;"
            ):
                ui.label(label).style("color:#6b7280; font-size:11px;")
                ui.label(value).style(f"color:{color}; font-size:11px; font-weight:bold;")

        def divider() -> None:
            ui.element("div").style("height:1px; background:#1e293b; margin:4px 0; width:100%;")

        def bar(pct: float, color: str) -> None:
            with ui.element("div").style(
                "height:5px; background:#1e293b; border-radius:2px; "
                "overflow:hidden; margin-bottom:5px; margin-top:1px; width:100%;"
            ):
                ui.element("div").style(
                    f"height:100%; width:{pct * 100:.0f}%; background:{color};"
                )

        stat("Stardate", f"{g.stardate:.1f}")
        divider()

        # Energy
        epct = max(0.0, min(1.0, g.energy / G.INITIAL_ENERGY))
        ecol = "#ef4444" if epct < 0.2 else "#eab308" if epct < 0.5 else "#22c55e"
        etxt = "#f87171" if epct < 0.2 else "#facc15" if epct < 0.5 else "#86efac"
        stat("Energy", str(g.energy), etxt)
        bar(epct, ecol)

        # Shields — show UP/DOWN state and pool level
        spct = max(0.0, min(1.0, g.shield_energy / G.MAX_SHIELDS))
        shield_label = "Shields ▲" if g.shields_up else "Shields ▽"
        shield_col = "#60a5fa" if g.shields_up else "#475569"
        stat(shield_label, str(g.shield_energy), shield_col)
        bar(spct, "#3b82f6" if g.shields_up else "#334155")

        divider()
        stat("Warp",      f"{g.warp_factor:.1f}", "#c084fc")
        stat("Klingons",  str(g.galaxy.total_klingons), "#f87171")
        tubes = g.torpedo_tubes
        stat("Torpedoes", f"{g.torpedoes}  [{tubes}t]", "#fb923c")

        # Damage (compact)
        damaged = [(name, lvl) for _, name, lvl in g.damage.all_systems() if lvl > 0]
        if damaged:
            divider()
            ui.label("DAMAGE").style(
                "color:#f87171; font-size:10px; font-weight:bold; margin-bottom:2px;"
            )
            for name, lvl in damaged:
                ui.label(f"  {name}: {lvl}t").style("color:#fca5a5; font-size:10px;")


# ---------------------------------------------------------------------------
# Galaxy map  (50%)
# ---------------------------------------------------------------------------

@ui.refreshable
def galaxy_map() -> None:
    g = get_state()

    # Galaxy map has 3-char codes so base font is slightly smaller than sector grid
    with ui.element("div").style(
        "background:black; padding:0.4em 0.6em; width:100%; height:100%; "
        "overflow:hidden; box-sizing:border-box; font-family:monospace; "
        "display:flex; flex-direction:column; "
        "font-size:clamp(9px, 2.0vmin, 32px);"
    ):
        if g is None:
            return

        data = g.get_galaxy_display()

        with ui.element("div").style(
            "display:flex; justify-content:space-between; margin-bottom:0.3em; flex-shrink:0;"
        ):
            ui.label("GALAXY MAP").style("color:#4ade80; font-size:0.85em; font-weight:bold;")
            ui.label("K=Klingons  B=Starbase  S=Stars").style("color:#374151; font-size:0.65em;")

        # Column headers
        with ui.element("div").style(
            "display:flex; margin-left:1.6em; margin-bottom:0.1em; flex-shrink:0;"
        ):
            for c in range(8):
                ui.label(str(c + 1)).style(
                    "flex:1; text-align:center; color:#374151; font-size:0.65em;"
                )

        # Grid rows — fill remaining height
        with ui.element("div").style(
            "display:flex; flex-direction:column; flex:1; min-height:0;"
        ):
            for r in range(8):
                with ui.element("div").style("display:flex; align-items:stretch; flex:1;"):
                    ui.label(str(r + 1)).style(
                        "width:1.6em; text-align:right; padding-right:0.2em; "
                        "color:#374151; font-size:0.65em; flex-shrink:0; "
                        "display:flex; align-items:center; justify-content:flex-end;"
                    )
                    for c in range(8):
                        code, is_current, scanned = data[r][c]
                        if is_current:
                            fg_c, border = "#4ade80", "2px solid #4ade80"
                            bg_c = "#052e16"
                        elif not scanned:
                            fg_c, border, bg_c = "#1f2937", "1px solid #111827", "transparent"
                        else:
                            k = int(code[0]) if code != "???" else 0
                            b = code[1] if code != "???" else "0"
                            if k > 0:
                                fg_c, border, bg_c = "#f87171", "1px solid #374151", "#1c0a0a"
                            elif b != "0":
                                fg_c, border, bg_c = "#22d3ee", "1px solid #374151", "#0a1c1c"
                            else:
                                fg_c, border, bg_c = "#6b7280", "1px solid #1f2937", "transparent"

                        ui.label(code).style(
                            f"flex:1; display:flex; align-items:center; "
                            f"justify-content:center; color:{fg_c}; background:{bg_c}; "
                            f"border:{border}; font-size:0.9em; box-sizing:border-box;"
                        )


# ---------------------------------------------------------------------------
# Message log
# ---------------------------------------------------------------------------

@ui.refreshable
def message_log() -> None:
    g = get_state()
    msgs = g.messages[-80:] if g else []
    with ui.scroll_area().classes("w-full bg-black msg-log-area").style(f"height:{_LOG_H};"):
        for msg in msgs:
            ui.label(msg).classes(
                f"{_msg_class(msg)} font-mono text-xs block whitespace-pre-wrap"
            ).style("line-height:1.4;")


# ---------------------------------------------------------------------------
# Command handling
# ---------------------------------------------------------------------------

_TOR_VERBS = {"tor", "t", "torp", "torpedo"}


def _refresh_all() -> None:
    sector_grid.refresh()
    status_panel.refresh()
    galaxy_map.refresh()
    message_log.refresh()
    ui.run_javascript(
        "const el = document.querySelector('.msg-log-area .scroll');"
        "if (el) el.scrollTop = el.scrollHeight;"
    )


def handle_command(input_el: ui.input) -> None:
    raw = input_el.value
    if not raw or not raw.strip():
        return
    input_el.set_value("")

    g = get_state()
    if g is None:
        return

    # Intercept bare torpedo command → open targeting dialog
    parts = raw.strip().lower().split()
    if parts[0] in _TOR_VERBS and len(parts) == 1:
        show_torpedo_dialog()
        return

    g.messages.append(f"> {raw}")
    G.parse_and_execute(g, raw)
    _refresh_all()

    if g.game_over:
        show_game_over_dialog(g)


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

def _torp_path(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """Bresenham-ish straight line from start to end (exclusive of start)."""
    r0, c0 = start
    r1, c1 = end
    dr, dc = r1 - r0, c1 - c0
    steps = max(abs(dr), abs(dc))
    if steps == 0:
        return [(r1, c1)]
    path, seen = [], set()
    for i in range(1, steps + 1):
        r = round(r0 + dr * i / steps)
        c = round(c0 + dc * i / steps)
        if (r, c) not in seen:
            path.append((r, c))
            seen.add((r, c))
    return path


def show_torpedo_dialog() -> None:
    g = get_state()
    if g is None:
        return

    tubes = g.torpedo_tubes
    max_fire = min(tubes, g.torpedoes)

    if max_fire == 0:
        g.messages.append("No torpedoes available!")
        message_log.refresh()
        return

    # Mutable dialog state
    sel: list[tuple[int, int]] = []
    num = {"val": 1}
    anim = {"torps": set(), "impacts": set(), "firing": False}

    with ui.dialog() as dlg, ui.card().style(
        "background:#0f172a; font-family:monospace; padding:16px; min-width:420px;"
    ):
        ui.label("-- TORPEDO CONTROL --").style(
            "color:#f87171; font-size:15px; font-weight:bold; "
            "text-align:center; width:100%; margin-bottom:4px;"
        )
        ui.label(
            f"Torpedoes: {g.torpedoes}   Tubes: {tubes}"
            + ("   (shields degrading accuracy)" if g.shields_up else "")
        ).style("color:#6b7280; font-size:10px; margin-bottom:10px;")

        # Count selector
        count_label = ui.label("Fire: 1 torpedo").style(
            "color:#fb923c; font-size:12px; font-weight:bold; margin-bottom:6px;"
        )
        count_btns: list[ui.button] = []
        with ui.element("div").style("display:flex; gap:8px; margin-bottom:10px;"):
            for n in range(1, max_fire + 1):
                b = ui.button(str(n)).props("dense").style(
                    "min-width:36px; font-family:monospace; font-weight:bold;"
                )
                count_btns.append(b)

        ui.label("Select target sector(s):").style(
            "color:#9ca3af; font-size:10px; margin-bottom:4px;"
        )

        @ui.refreshable
        def torp_sector_grid() -> None:
            display = g.get_sector_display()
            sel_set = set(sel)

            with ui.element("div").style("display:flex; flex-direction:column; gap:2px;"):
                for r in range(8):
                    with ui.element("div").style("display:flex; gap:2px;"):
                        for c in range(8):
                            entry = display.get((r, c))
                            is_ship = (r, c) == (g.s_pos.row, g.s_pos.col)
                            sym = entry[0] if entry else "·"
                            etype = entry[1] if entry else "empty"

                            # Animation layers take priority over normal display
                            if (r, c) in anim["impacts"]:
                                sym, bg, border, fg = (
                                    "*", "#7f1d1d", "2px solid #fbbf24", "#fef08a"
                                )
                            elif (r, c) in anim["torps"]:
                                sym, bg, border, fg = (
                                    "o", "#431407", "1px solid #f97316", "#fb923c"
                                )
                            elif (r, c) in sel_set:
                                bg, border, fg = "#7f1d1d", "2px solid #ef4444", "#fca5a5"
                            elif etype == "ship":
                                bg, border, fg = "#052e16", "1px solid #4ade80", "#4ade80"
                            elif etype == "klingon":
                                bg, border, fg = "#1c0a0a", "1px solid #dc2626", "#f87171"
                            elif etype == "starbase":
                                bg, border, fg = "#0a1c1c", "1px solid #22d3ee", "#22d3ee"
                            elif etype == "star":
                                bg, border, fg = "transparent", "1px solid #292524", "#facc15"
                            else:
                                bg, border, fg = "transparent", "1px solid #1f2937", "#374151"

                            def on_cell_click(r: int = r, c: int = c) -> None:
                                if is_ship or anim["firing"]:
                                    return
                                if (r, c) in sel:
                                    sel.remove((r, c))
                                elif len(sel) < num["val"]:
                                    sel.append((r, c))
                                torp_sector_grid.refresh()
                                _update_sel_label()

                            ui.button(sym).on("click", on_cell_click).style(
                                f"width:36px; height:36px; min-width:36px; padding:0; "
                                f"background:{bg}; color:{fg}; border:{border}; "
                                f"font-family:monospace; font-size:13px; font-weight:bold;"
                            ).props("dense flat")

        torp_sector_grid()

        sel_label = ui.label("Targets: none selected").style(
            "color:#9ca3af; font-size:10px; margin-top:6px;"
        )

        def _update_sel_label() -> None:
            if sel:
                sel_label.text = "Targets: " + "  ".join(f"({r+1},{c+1})" for r, c in sel)
            else:
                sel_label.text = "Targets: none selected"

        def set_count(n: int) -> None:
            num["val"] = n
            while len(sel) > n:
                sel.pop()
            count_label.text = f"Fire: {n} torpedo{'es' if n != 1 else ''}"
            for i, b in enumerate(count_btns):
                active = (i + 1 == n)
                b.style(
                    f"min-width:36px; font-family:monospace; font-weight:bold; "
                    f"background:{'#dc2626' if active else '#374151'}; "
                    f"color:{'white' if active else '#9ca3af'};"
                )
            torp_sector_grid.refresh()
            _update_sel_label()

        for i, b in enumerate(count_btns):
            b.on("click", lambda n=i + 1: set_count(n))
        set_count(1)

        with ui.element("div").style("display:flex; gap:8px; margin-top:12px;"):
            fire_btn = ui.button("FIRE TORPEDOES").style(
                "background:#dc2626; color:white; font-family:monospace; font-weight:bold;"
            ).props("dense")
            cancel_btn = ui.button("CANCEL").style(
                "background:#374151; color:#9ca3af; font-family:monospace;"
            ).props("dense")

        async def fire_animated() -> None:
            if not sel:
                ui.notify("Select at least one target sector first.", color="warning")
                return

            targets = list(sel)
            anim["firing"] = True
            fire_btn.disable()
            cancel_btn.disable()

            ship = (g.s_pos.row, g.s_pos.col)
            paths = [_torp_path(ship, t) for t in targets]

            # Animate each torpedo sequentially
            for path, target in zip(paths, targets):
                for pos in path:
                    anim["torps"] = {pos}
                    anim["impacts"] = set()
                    torp_sector_grid.refresh()
                    await asyncio.sleep(0.07)
                # Impact flash for this torpedo
                anim["torps"] = set()
                anim["impacts"] = {target}
                torp_sector_grid.refresh()
                await asyncio.sleep(0.3)

            # Clean up and execute
            anim["torps"] = set()
            anim["impacts"] = set()
            dlg.close()
            g.messages.append(f"> tor {' '.join(f'{r+1} {c+1}' for r, c in targets)}")
            g.cmd_torpedo(targets)
            _refresh_all()
            if g.game_over:
                show_game_over_dialog(g)

        fire_btn.on("click", fire_animated)
        cancel_btn.on("click", dlg.close)

    dlg.open()


def show_help_dialog() -> None:
    with ui.dialog() as dlg, ui.card().classes("bg-gray-900 font-mono max-w-xl"):
        ui.label("COMMAND REFERENCE").classes("text-green-400 font-bold mb-3")
        rows = [
            ("m QR QC SR SC", "Warp to quadrant+sector (e.g. m 6 2 3 5 or m6235)"),
            ("m SR SC",        "Impulse within quadrant (e.g. m 3 5 or m35)"),
            ("w FACTOR",       "Set warp factor 0.1–8 (e.g. w5 or w2.5, default 5)"),
            ("pha POWER",      "Fire phasers with POWER energy units"),
            ("tor",             "Open torpedo targeting dialog (clickable sector map)"),
            ("shup / s",       "Raise shields (small energy cost)"),
            ("shdn / sd",      "Lower shields (free; pool energy retained)"),
            ("ene N",          "Transfer N energy to shields (neg = reclaim from shields)"),
            ("max",            "Divert maximum energy to shields"),
            ("lrs",            "Long range scan (3×3 quadrant view)"),
            ("dam",            "Damage report"),
            ("dock",           "Dock with adjacent starbase (restores main energy only)"),
            ("status",         "Full status report"),
            ("help",           "This message"),
            ("quit",           "Surrender"),
        ]
        with ui.grid(columns=2).classes("gap-x-4 gap-y-1 w-full"):
            for cmd, desc in rows:
                ui.label(cmd).classes("text-yellow-400 text-sm")
                ui.label(desc).classes("text-gray-300 text-sm")
        ui.label("Single-letter abbreviations: s=shup  sd=shdn  e=ene  p=pha  t=tor").classes(
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
        ui.label(f"Klingons remaining: {g.galaxy.total_klingons}").classes("text-gray-400 mt-2 text-sm")

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
                "easy":   "Cadet   — 10 Klingons, 30 stardates",
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
    ui.dark_mode().enable()

    # Full-viewport, no scroll.
    # NiceGUI's own CSS sets align-items:flex-start and gap/padding on
    # .nicegui-content, which collapses children to content-width.
    # Quasar's q-layout stack also needs explicit heights.
    ui.add_css("""
        html, body {
            margin: 0; padding: 0;
            width: 100%; height: 100%;
            overflow: hidden; background: black;
        }
        #app, .q-app {
            width: 100% !important; height: 100vh !important;
            overflow: hidden !important;
        }
        .q-layout {
            width: 100% !important; height: 100vh !important;
            min-height: unset !important; overflow: hidden !important;
        }
        .q-page-container {
            width: 100% !important; height: 100vh !important;
            min-height: unset !important;
            padding: 0 !important; overflow: hidden !important;
        }
        .q-page {
            width: 100% !important; height: 100vh !important;
            min-height: unset !important; overflow: hidden !important;
        }
        .nicegui-content {
            /* override NiceGUI defaults: align-items, gap, padding */
            align-items: stretch !important;
            gap: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            max-width: none !important;
            height: 100vh !important;
            flex-direction: column !important;
            overflow: hidden !important;
        }
    """)

    def start_game(klingons: int, stardates: int) -> None:
        new_game(klingons=klingons, starbases=4, stardates=stardates)
        sector_grid.refresh()
        status_panel.refresh()
        galaxy_map.refresh()
        message_log.refresh()

    # ── Title bar ──────────────────────────────────────────────────────────
    with ui.element("div").style(
        f"display:flex; align-items:center; justify-content:space-between; "
        f"padding:0 12px; background:#020617; border-bottom:1px solid #1e293b; "
        f"height:{_TITLE_H}; flex-shrink:0;"
    ):
        ui.label("★  STAR TREK").style(
            "color:#4ade80; font-family:monospace; font-weight:bold; font-size:15px;"
        )
        ui.label("NiceGUI / EGATrek clone").style("color:#374151; font-family:monospace; font-size:10px;")
        ui.button("New Game", on_click=lambda: show_new_game_dialog(start_game)).classes(
            "bg-gray-800 text-green-400 font-mono text-xs"
        ).props("dense flat")

    # ── Three-panel top row ────────────────────────────────────────────────
    with ui.element("div").style(
        f"display:flex; height:{_PANELS_H}; flex-shrink:0; overflow:hidden; "
        f"border-bottom:1px solid #1e293b;"
    ):
        with _panel("25%"):
            sector_grid()
        with _panel("25%"):
            status_panel()
        with _panel("50%", border_right=False):
            galaxy_map()

    # ── Message log ────────────────────────────────────────────────────────
    with ui.element("div").style(
        "flex-shrink:0; overflow:hidden; padding:4px 8px 0 8px; background:black;"
    ):
        message_log()

    # ── Command input ──────────────────────────────────────────────────────
    with ui.element("div").style(
        f"display:flex; align-items:center; gap:8px; padding:6px 10px; "
        f"background:#020617; border-top:1px solid #1e293b; "
        f"height:{_CMD_H}; flex-shrink:0; box-sizing:border-box;"
    ):
        ui.label(">").style(
            "color:#4ade80; font-family:monospace; font-weight:bold; font-size:16px;"
        )
        cmd_input = (
            ui.input(placeholder="m 6 2 3 5  |  m 3 5  |  w 6  |  pha 500  |  tor 3 5  |  shup  |  ene 500  |  lrs")
            .style("flex:1; font-family:monospace;")
            .classes("text-green-300")
            .props("dark dense standout outlined")
        )
        cmd_input.on("keydown.enter", lambda: handle_command(cmd_input))
        ui.button("SEND", on_click=lambda: handle_command(cmd_input)).classes(
            "bg-green-800 text-green-200 font-mono text-sm"
        ).props("dense")
        ui.button("TORPEDO", on_click=show_torpedo_dialog).classes(
            "bg-red-900 text-red-300 font-mono text-sm"
        ).props("dense")
        ui.button("HELP", on_click=show_help_dialog).classes(
            "bg-gray-800 text-gray-300 font-mono text-sm"
        ).props("dense")

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
