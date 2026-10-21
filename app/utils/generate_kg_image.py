"""Generate authentic Neo4j Browser Knowledge Graph visualization image.

Directly queries the live Neo4j graph database populated from kgraph.xlsx / investigation.csv:
- Circular node bubbles matching Neo4j Browser styling:
  * Domain: #F43F5E (Rose Pink)
  * Scenario: #3B82F6 (Blue)
  * Skill: #8B5CF6 (Purple)
  * InvestigationStep: #10B981 (Green)
  * Tool: #F59E0B (Amber)
  * EvidenceType: #06B6D4 (Cyan)
- Relationship arrows with Neo4j-style pill labels:
  * [:HAS_SCENARIO], [:GOVERNED_BY], [:HAS_STEP], [:MAY_USE_TOOL], [:REQUIRES_EVIDENCE], [:DEPENDS_ON]
- Live Neo4j Browser UI frame with active Cypher query bar and Node/Relationship summary badges.
"""

from pathlib import Path
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = ROOT / "app" / "ui" / "assets"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "knowledge_graph_tree.png"


def query_live_neo4j():
    """Fetch active graph structure from live Neo4j instance."""
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=None)
    
    with driver.session() as session:
        # Fetch domains
        domains = [r["name"] for r in session.run("MATCH (d:Domain) RETURN d.name as name ORDER BY name")]
        
        # Fetch target LOGIN scenario with steps, tools, and evidence
        scenario_record = session.run("""
            MATCH (d:Domain {name: 'LOGIN'})-[:HAS_SCENARIO]->(s:Scenario {id: 'delegated_admin_deactivation'})
            OPTIONAL MATCH (s)-[:GOVERNED_BY]->(sk:Skill)
            RETURN s.id as id, s.name as name, s.description as description, sk.id as skill_file
        """).single()
        
        steps_records = list(session.run("""
            MATCH (s:Scenario {id: 'delegated_admin_deactivation'})-[:HAS_STEP]->(st:InvestigationStep)
            OPTIONAL MATCH (st)-[:MAY_USE_TOOL]->(t:Tool)
            OPTIONAL MATCH (st)-[:REQUIRES_EVIDENCE]->(e:EvidenceType)
            OPTIONAL MATCH (st)-[:DEPENDS_ON]->(dep:InvestigationStep)
            RETURN 
                st.id as id,
                st.order as order,
                st.name as name,
                st.stage as stage,
                collect(DISTINCT t.name) as tools,
                collect(DISTINCT e.name) as evidence,
                collect(DISTINCT dep.id) as depends_on
            ORDER BY st.order
        """))

        # Fetch other scenarios under LOGIN
        other_scenarios = [r["name"] for r in session.run("""
            MATCH (d:Domain {name: 'LOGIN'})-[:HAS_SCENARIO]->(s:Scenario)
            WHERE s.id <> 'delegated_admin_deactivation'
            RETURN s.name as name LIMIT 6
        """)]

        counts = {
            "domains": session.run("MATCH (n:Domain) RETURN count(n) as c").single()["c"],
            "scenarios": session.run("MATCH (n:Scenario) RETURN count(n) as c").single()["c"],
            "steps": session.run("MATCH (n:InvestigationStep) RETURN count(n) as c").single()["c"],
            "tools": session.run("MATCH (n:Tool) RETURN count(n) as c").single()["c"],
            "evidence": session.run("MATCH (n:EvidenceType) RETURN count(n) as c").single()["c"],
            "relationships": session.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
        }

    driver.close()
    return domains, scenario_record, steps_records, other_scenarios, counts


def draw_circular_node(ax, cx, cy, radius, label, subtext, color, border_color="#ffffff", line_w=2.0):
    """Draw a circular bubble node as rendered in Neo4j Browser."""
    circle = patches.Circle((cx, cy), radius, facecolor=color, edgecolor=border_color, linewidth=line_w, zorder=4)
    ax.add_patch(circle)
    if subtext:
        ax.text(cx, cy + 0.15, label, fontsize=9, fontweight="bold", color="#ffffff", ha="center", va="center", zorder=5)
        ax.text(cx, cy - 0.22, subtext[:22], fontsize=7.5, color="#f1f5f9", ha="center", va="center", zorder=5)
    else:
        ax.text(cx, cy, label, fontsize=9.5, fontweight="bold", color="#ffffff", ha="center", va="center", zorder=5)


def draw_relationship(ax, x1, y1, x2, y2, rel_name, color="#94a3b8", rad=0.0):
    """Draw a directed relationship arrow with Neo4j-style label pill."""
    # Directed arrow
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.8,
                                connectionstyle=f"arc3,rad={rad}", mutation_scale=15),
                zorder=2)
    # Midpoint label
    mx = (x1 + x2) / 2.0
    my = (y1 + y2) / 2.0 + (rad * 0.8)
    pill = patches.FancyBboxPatch((mx - 0.9, my - 0.18), 1.8, 0.36, boxstyle="round,pad=0.08",
                                  facecolor="#1e293b", edgecolor=color, linewidth=1.0, zorder=3)
    ax.add_patch(pill)
    ax.text(mx, my, rel_name, fontsize=7, fontweight="bold", color="#e2e8f0", ha="center", va="center", zorder=3)


def create_knowledge_graph_image():
    domains, target_scen, steps_data, other_scenarios, counts = query_live_neo4j()

    fig, ax = plt.subplots(figsize=(30, 18), dpi=150)
    fig.patch.set_facecolor("#1e212b")  # Authentic Neo4j Browser dark canvas
    ax.set_facecolor("#1e212b")
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 18)
    ax.axis("off")

    # =========================================================================
    # NEO4J BROWSER TOP BAR & CYPHER PROMPT
    # =========================================================================
    # Browser window header
    top_bar = patches.Rectangle((0, 17.0), 30, 1.0, facecolor="#14171f", zorder=1)
    ax.add_patch(top_bar)
    ax.text(1.2, 17.5, "neo4j$", fontsize=13, fontweight="bold", color="#38bdf8")
    ax.text(2.6, 17.5, "MATCH (d:Domain {name: 'LOGIN'})-[:HAS_SCENARIO]->(s)-[:HAS_STEP]->(step) RETURN * // Live Database from kgraph.xlsx",
            fontsize=11, color="#f8fafc", family="monospace")

    # Metrics Summary Bar
    sum_bar = patches.Rectangle((0, 16.3), 30, 0.7, facecolor="#0f172a", zorder=1)
    ax.add_patch(sum_bar)
    summary_text = (f"LIVE NEO4J DATABASE (bolt://localhost:7687)  |  "
                    f"Nodes: {counts['domains']} Domains, {counts['scenarios']} Scenarios, "
                    f"{counts['steps']} InvestigationSteps, {counts['tools']} Tools, {counts['evidence']} EvidenceTypes  |  "
                    f"Total Relationships: {counts['relationships']}")
    ax.text(1.2, 16.65, summary_text, fontsize=9.5, fontweight="bold", color="#38bdf8")

    # =========================================================================
    # NEO4J BROWSER LEGEND (CIRCULAR BADGES)
    # =========================================================================
    palette = [
        ("Domain (4)", "#f43f5e"),
        ("Scenario (18)", "#3b82f6"),
        ("Skill (18)", "#8b5cf6"),
        ("InvestigationStep (120)", "#10b981"),
        ("Tool (11)", "#f59e0b"),
        ("EvidenceType (135)", "#06b6d4")
    ]
    for idx, (label, color) in enumerate(palette):
        bx = 18.0 + (idx * 1.95)
        circle = patches.Circle((bx, 17.5), 0.22, facecolor=color, edgecolor="#ffffff", linewidth=1.2, zorder=6)
        ax.add_patch(circle)
        ax.text(bx + 0.32, 17.5, label.split()[0], fontsize=8, color="#cbd5e1", va="center", zorder=6)

    # =========================================================================
    # SECTION 1: ALL 4 DOMAINS (Left Column, x = 3.0)
    # =========================================================================
    ax.text(3.0, 15.6, "(:Domain) Nodes", fontsize=11, fontweight="bold", color="#f43f5e", ha="center")
    dom_coords = {
        "LOGIN": (3.0, 11.5),
        "RECORD": (3.0, 7.5),
        "OBJECT": (3.0, 4.5),
        "APPLICATION": (3.0, 1.8)
    }

    for dom_name, (dx, dy) in dom_coords.items():
        is_target = dom_name == "LOGIN"
        r = 1.1 if is_target else 0.85
        border = "#ef4444" if is_target else "#fda4af"
        lw = 3.0 if is_target else 1.5
        draw_circular_node(ax, dx, dy, r, f"Domain", dom_name, "#f43f5e", border_color=border, line_w=lw)

    # Annotation Point 1 on LOGIN
    p1 = patches.Circle((1.5, 12.3), 0.38, facecolor="#ef4444", edgecolor="#ffffff", linewidth=2.0, zorder=7)
    ax.add_patch(p1)
    ax.text(1.5, 12.3, "1", fontsize=11, fontweight="bold", color="#ffffff", ha="center", va="center", zorder=8)
    ax.text(1.5, 13.0, "POINT [1]\nDomain Node", fontsize=8.5, fontweight="bold", color="#f87171", ha="center", va="center")

    # =========================================================================
    # SECTION 2: SCENARIO & SKILL NODES (x = 8.5)
    # =========================================================================
    ax.text(8.5, 15.6, "(:Scenario) Nodes", fontsize=11, fontweight="bold", color="#60a5fa", ha="center")
    
    # Target Root Cause Scenario
    sc_target_x, sc_target_y = 8.5, 11.5
    draw_relationship(ax, 4.1, 11.5, sc_target_x - 1.25, sc_target_y, "HAS_SCENARIO", color="#60a5fa")
    draw_circular_node(ax, sc_target_x, sc_target_y, 1.25, "Scenario", "delegated_admin\ndeactivation", "#3b82f6", border_color="#93c5fd", line_w=3.0)

    # Annotation Point 2 on Target Scenario
    p2 = patches.Circle((7.0, 12.6), 0.38, facecolor="#f59e0b", edgecolor="#ffffff", linewidth=2.0, zorder=7)
    ax.add_patch(p2)
    ax.text(7.0, 12.6, "2", fontsize=11, fontweight="bold", color="#ffffff", ha="center", va="center", zorder=8)
    ax.text(7.0, 13.3, "POINT [2]\nRoot Cause Scenario", fontsize=8.5, fontweight="bold", color="#fbbf24", ha="center", va="center")

    # Governed by Skill Node
    sk_x, sk_y = 8.5, 7.5
    draw_relationship(ax, sc_target_x, sc_target_y - 1.25, sk_x, sk_y + 0.95, "GOVERNED_BY", color="#c084fc")
    draw_circular_node(ax, sk_x, sk_y, 0.95, "Skill", "delegated_admin\n_deactivation.md", "#8b5cf6", border_color="#c084fc", line_w=2.0)

    # Other scenarios cluster (showing graph connectivity as in Neo4j)
    other_ys = [15.2, 13.8, 9.6, 5.2, 3.6, 2.0]
    for idx, sc_name in enumerate(other_scenarios[:6]):
        oy = other_ys[idx]
        draw_relationship(ax, 3.8, 11.5, 7.6, oy, "HAS_SCENARIO", color="#334155", rad=-0.08)
        draw_circular_node(ax, 8.5, oy, 0.65, "Scenario", sc_name[:14], "#1e3a8a", border_color="#3b82f6", line_w=1.0)

    # =========================================================================
    # SECTION 3: INVESTIGATION STEPS DAG (x = 14.5)
    # =========================================================================
    ax.text(14.5, 15.6, "(:InvestigationStep) DAG", fontsize=11, fontweight="bold", color="#34d399", ha="center")

    # Connect Scenario to Step 1
    draw_relationship(ax, sc_target_x + 1.25, sc_target_y, 13.3, 14.3, "HAS_STEP", color="#10b981", rad=-0.08)

    # Annotation Point 3 on Step DAG Traversal
    p3 = patches.Circle((12.7, 15.6), 0.38, facecolor="#10b981", edgecolor="#ffffff", linewidth=2.0, zorder=7)
    ax.add_patch(p3)
    ax.text(12.7, 15.6, "3", fontsize=11, fontweight="bold", color="#ffffff", ha="center", va="center", zorder=8)
    ax.text(12.7, 16.3, "POINT [3]\nStep DAG Traversal", fontsize=8.5, fontweight="bold", color="#34d399", ha="center", va="center")

    step_coords = {}
    step_start_y = 14.3
    step_y_spacing = 2.0

    for idx, st in enumerate(steps_data):
        sy = step_start_y - (idx * step_y_spacing)
        step_coords[st["id"]] = (14.5, sy)
        order = st["order"]
        name = st["name"]
        color = "#10b981" if "resolution" not in st["stage"] else "#2563eb"
        draw_circular_node(ax, 14.5, sy, 0.85, f"Step {order}", name[:16], color, border_color="#6ee7b7", line_w=2.0)

        # Draw DEPENDS_ON relationship between sequential steps
        if idx > 0:
            prev_y = step_start_y - ((idx - 1) * step_y_spacing)
            draw_relationship(ax, 14.5, prev_y - 0.85, 14.5, sy + 0.85, "DEPENDS_ON", color="#34d399")

    # =========================================================================
    # SECTION 4: TOOLS & EVIDENCE TYPE NODES (x = 21.0 & 26.5)
    # =========================================================================
    ax.text(21.0, 15.6, "(:Tool) Nodes", fontsize=11, fontweight="bold", color="#fbbf24", ha="center")
    ax.text(26.5, 15.6, "(:EvidenceType) Nodes", fontsize=11, fontweight="bold", color="#22d3ee", ha="center")

    for idx, st in enumerate(steps_data):
        sy = step_start_y - (idx * step_y_spacing)
        tools = st["tools"]
        evidence = st["evidence"]

        # Tool node
        if tools:
            tool_name = tools[0]
            draw_relationship(ax, 15.35, sy, 20.0, sy, "MAY_USE_TOOL", color="#f59e0b")
            draw_circular_node(ax, 21.0, sy, 0.75, "Tool", tool_name.split(".")[-1], "#d97706", border_color="#fde68a", line_w=1.5)

        # EvidenceType node
        if evidence:
            ev_name = evidence[0]
            draw_relationship(ax, 21.75 if tools else 15.35, sy, 25.6, sy, "REQUIRES_EVIDENCE", color="#06b6d4")
            draw_circular_node(ax, 26.5, sy, 0.75, "Evidence", ev_name[:15], "#0891b2", border_color="#a5f3fc", line_w=1.5)

    # Save final Neo4j browser canvas
    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=150, facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    print(f"Neo4j Browser graph generated at: {OUTPUT_FILE}")


if __name__ == "__main__":
    create_knowledge_graph_image()
