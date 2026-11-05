"""
Generates a polished system architecture diagram for OPSRECALL and saves to assets/architecture.png.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

output_path = Path("assets/architecture.png")
output_path.parent.mkdir(parents=True, exist_ok=True)

fig, ax = plt.subplots(figsize=(14, 9), dpi=200)
fig.patch.set_facecolor("#0b0f19")
ax.set_facecolor("#0b0f19")
ax.set_xlim(0, 14)
ax.set_ylim(0, 9)
ax.axis("off")

# Title
ax.text(
    7.0, 8.5, "OPSRECALL SYSTEM ARCHITECTURE",
    ha="center", va="center", color="#38bdf8", fontsize=18, fontweight="bold",
    fontfamily="sans-serif"
)
ax.text(
    7.0, 8.1, "Change-Aware Incident Intelligence Agent powered by Hindsight & Groq",
    ha="center", va="center", color="#94a3b8", fontsize=11, fontfamily="sans-serif"
)

# Helper for drawing rounded boxes
def draw_card(ax, x, y, w, h, title, subtitle, fill_color, border_color, title_color="#f8fafc"):
    rect = patches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.12,rounding_size=0.2",
        linewidth=1.8, edgecolor=border_color, facecolor=fill_color
    )
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h - 0.35, title, ha="center", va="center", color=title_color, fontsize=11, fontweight="bold")
    ax.text(x + w / 2, y + (h - 0.4) / 2, subtitle, ha="center", va="center", color="#cbd5e1", fontsize=8.5, multialignment="center")

# Layer 1: Streamlit Dashboard UI
draw_card(ax, 1.0, 6.2, 12.0, 1.3,
          "OPERATIONAL SRE CONSOLE (Streamlit + Plotly)",
          "Command Center | Incident Console | Investigation & Comparison | Memory Explorer | Learning Center | Evaluation Lab",
          "#1e293b", "#0284c7", "#38bdf8")

# Layer 2: Core Orchestration Controller
draw_card(ax, 4.0, 4.5, 6.0, 1.1,
          "INCIDENT INVESTIGATION CONTROLLER",
          "Input Validation | Telemetry Synthesis | Mode Switching (Memory ON vs OFF)",
          "#1e293b", "#3b82f6")

# Layer 3: Left = Hindsight Memory, Right = Groq LLM
draw_card(ax, 1.0, 2.4, 5.0, 1.5,
          "HINDSIGHT PERSISTENT MEMORY",
          "Dedicated Bank: opsrecall-demo\n• RETAIN: Verified Outcomes & Failed Fixes\n• RECALL: TEMPR Semantic & Change Search\n• REFLECT: Cross-Incident Macro Patterns",
          "#0f172a", "#06b6d4", "#22d3ee")

draw_card(ax, 8.0, 2.4, 5.0, 1.5,
          "GROQ REASONING ENGINE",
          "Model: llama-3.3-70b-versatile\n• Structured Hypothesis Generation (Top-3)\n• Actionable Diagnostics & SOP Steps\n• Rigorous Historical Evidence Attribution",
          "#0f172a", "#f59e0b", "#fbbf24")

# Layer 4: Evidence & Decision Synthesis Layer
draw_card(ax, 3.5, 0.7, 7.0, 1.2,
          "EVIDENCE & LEARNING LOOP",
          "Human Engineer Resolution Feedback  ->  Hindsight Retain (document_id)\nSQLite Local Audit Log (Incidents, Investigations, Benchmark Runs)",
          "#1e293b", "#10b981", "#34d399")

# Arrows
def draw_arrow(ax, x1, y1, x2, y2, color="#64748b", text=""):
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>", color=color, lw=2, mutation_scale=15)
    )
    if text:
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        ax.text(mid_x, mid_y, text, ha="center", va="center", color="#94a3b8", fontsize=8,
                bbox=dict(boxstyle="square,pad=0.2", facecolor="#0b0f19", edgecolor="none"))

# Down from UI to Controller
draw_arrow(ax, 7.0, 6.2, 7.0, 5.6, "#38bdf8", "Incident & Telemetry")

# Controller to Hindsight
draw_arrow(ax, 5.5, 4.5, 3.5, 3.9, "#06b6d4", "TEMPR Recall Query")

# Controller to Groq
draw_arrow(ax, 8.5, 4.5, 10.5, 3.9, "#f59e0b", "Structured Prompt")

# Hindsight to Groq (Memory grounding)
draw_arrow(ax, 6.0, 3.15, 8.0, 3.15, "#22d3ee", "Recalled Facts & Failed Fixes")

# Hindsight to Learning Loop
draw_arrow(ax, 3.5, 2.4, 4.5, 1.9, "#06b6d4", "")

# Groq to Learning Loop
draw_arrow(ax, 10.5, 2.4, 9.5, 1.9, "#10b981", "Investigation Result")

# Learning Loop Retain back to Hindsight
ax.annotate(
    "", xy=(1.5, 2.4), xytext=(3.5, 1.3),
    arrowprops=dict(arrowstyle="-|>", color="#10b981", lw=2, connectionstyle="arc3,rad=-0.25", mutation_scale=15)
)
ax.text(1.8, 1.6, "Verified Retain", color="#34d399", fontsize=8.5, fontweight="bold")

plt.tight_layout()
plt.savefig(output_path, facecolor=fig.get_facecolor(), edgecolor="none", dpi=200)
plt.close()
print(f"Architecture diagram generated successfully at {output_path}")

