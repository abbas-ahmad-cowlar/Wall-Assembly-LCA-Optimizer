"""Wall Assembly LCA Optimizer - User-Friendly GUI

A single-window application with:
- Step-by-step progress page → Results page (with back button)
- Clear layer editing with live preview
- Visual feedback when values change

Usage:
    python run_gui.py
"""

import sys
import logging
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import List, Optional
import time

# Suppress verbose logging
logging.getLogger().setLevel(logging.WARNING)


class WallOptimizerApp:
    """Main application - single window with multiple pages."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Wall Assembly LCA Optimizer")
        self.root.geometry("950x700")
        self.root.configure(bg="#f5f6fa")
        self.root.minsize(900, 650)
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - 475
        y = (self.root.winfo_screenheight() // 2) - 350
        self.root.geometry(f"+{x}+{y}")
        
        # Data
        self.wall = None
        self.materials = None
        self.original_wall = None  # For comparison
        
        # Import dependencies
        from config import R_SI, R_SE, TARGET_U, TOLERANCE
        from optimizer import Candidate
        from physics import calculate_layer_r_value, calculate_layer_lca_impact
        
        self.R_SI = R_SI
        self.R_SE = R_SE
        self.TARGET_U = TARGET_U
        self.TOLERANCE = TOLERANCE
        self.Candidate = Candidate
        self.calc_r = calculate_layer_r_value
        self.calc_lca = calculate_layer_lca_impact
        
        # Container for pages
        self.container = tk.Frame(self.root, bg="#f5f6fa")
        self.container.pack(fill="both", expand=True)
        
        # Pages
        self.pages = {}
        self.current_page = None
        
        self._create_progress_page()
        self._create_results_page()
        self._create_edit_page()
        
        self._show_page("progress")
    
    def _show_page(self, page_name: str):
        """Switch to a different page."""
        if self.current_page:
            self.pages[self.current_page].pack_forget()
        
        self.pages[page_name].pack(fill="both", expand=True)
        self.current_page = page_name
    
    # ==================== PROGRESS PAGE ====================
    
    def _create_progress_page(self):
        """Create the progress/loading page."""
        page = tk.Frame(self.container, bg="#2c3e50")
        self.pages["progress"] = page
        
        # Center content
        center = tk.Frame(page, bg="#2c3e50")
        center.place(relx=0.5, rely=0.5, anchor="center")
        
        # Logo/Title
        tk.Label(
            center,
            text="🏠",
            font=("Segoe UI", 48),
            bg="#2c3e50",
            fg="white"
        ).pack(pady=(0, 10))
        
        tk.Label(
            center,
            text="Wall Assembly LCA Optimizer",
            font=("Segoe UI", 24, "bold"),
            bg="#2c3e50",
            fg="white"
        ).pack()
        
        tk.Label(
            center,
            text="Finding the optimal wall configuration...",
            font=("Segoe UI", 12),
            bg="#2c3e50",
            fg="#bdc3c7"
        ).pack(pady=(5, 30))
        
        # Steps
        steps_frame = tk.Frame(center, bg="#34495e", padx=40, pady=25)
        steps_frame.pack()
        
        self.step_widgets = []
        steps = [
            ("📂", "Loading Material Data"),
            ("🧹", "Processing & Normalizing"),
            ("⚡", "Running Optimization"),
            ("✅", "Complete!")
        ]
        
        for i, (icon, text) in enumerate(steps):
            row = tk.Frame(steps_frame, bg="#34495e")
            row.pack(fill="x", pady=6)
            
            lbl = tk.Label(
                row,
                text=f"  {icon}  {text}",
                font=("Segoe UI", 13),
                bg="#34495e",
                fg="#7f8c8d",
                anchor="w",
                width=30
            )
            lbl.pack(side="left")
            
            status = tk.Label(
                row,
                text="○",
                font=("Segoe UI", 14),
                bg="#34495e",
                fg="#7f8c8d"
            )
            status.pack(side="right", padx=10)
            
            self.step_widgets.append((lbl, status))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(center, length=350, mode="determinate")
        self.progress_bar.pack(pady=25)
    
    def _update_step(self, index: int, state: str):
        """Update step visual state."""
        lbl, status = self.step_widgets[index]
        
        if state == "running":
            lbl.configure(fg="#3498db")
            status.configure(text="◐", fg="#3498db")
        elif state == "done":
            lbl.configure(fg="#2ecc71")
            status.configure(text="●", fg="#2ecc71")
        
        self.progress_bar["value"] = (index + 1) * 25
        self.root.update()
    
    def run_optimization(self):
        """Run optimization with visual progress."""
        try:
            # Step 1
            self._update_step(0, "running")
            time.sleep(0.2)
            
            from data_loader import load_data
            self.materials = load_data()
            self._update_step(0, "done")
            
            # Step 2
            self._update_step(1, "running")
            time.sleep(0.3)
            self._update_step(1, "done")
            
            # Step 3
            self._update_step(2, "running")
            
            from optimizer import run_optimization
            self.wall = run_optimization()
            self._update_step(2, "done")
            
            if self.wall:
                # Save original for comparison
                self.original_wall = [
                    self.Candidate(c.material, c.thickness, c.r_val, c.lca_val)
                    for c in self.wall
                ]
                
                # Step 4
                self._update_step(3, "done")
                time.sleep(0.5)
                
                # Switch to results
                self._refresh_results_page()
                self._show_page("results")
            else:
                messagebox.showerror("Error", "No valid wall assembly found!")
                
        except Exception as e:
            messagebox.showerror("Error", f"Optimization failed:\n{e}")
    
    # ==================== RESULTS PAGE ====================
    
    def _create_results_page(self):
        """Create the results page."""
        page = tk.Frame(self.container, bg="#f5f6fa")
        self.pages["results"] = page
        
        # Header bar
        header = tk.Frame(page, bg="#2c3e50", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        header_content = tk.Frame(header, bg="#2c3e50")
        header_content.pack(fill="both", expand=True, padx=20, pady=15)
        
        tk.Label(
            header_content,
            text="🏠 Wall Assembly Results",
            font=("Segoe UI", 18, "bold"),
            bg="#2c3e50",
            fg="white"
        ).pack(side="left")
        
        # Metrics bar
        self.metrics_bar = tk.Frame(page, bg="#34495e", height=90)
        self.metrics_bar.pack(fill="x")
        self.metrics_bar.pack_propagate(False)
        
        # Main content
        main = tk.Frame(page, bg="#f5f6fa", padx=25, pady=15)
        main.pack(fill="both", expand=True)
        
        # Instructions
        tk.Label(
            main,
            text="📋 Layer Configuration — Click 'Edit' to modify any layer",
            font=("Segoe UI", 13, "bold"),
            bg="#f5f6fa",
            fg="#2c3e50"
        ).pack(anchor="w", pady=(0, 10))
        
        # Table using Treeview for proper alignment
        table_frame = tk.Frame(main, bg="white")
        table_frame.pack(fill="both", expand=True)
        
        # Create Treeview
        cols = ("layer", "material", "thickness", "r_value", "lca", "changed")
        self.results_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        
        # Define headings
        self.results_tree.heading("layer", text="Layer")
        self.results_tree.heading("material", text="Material")
        self.results_tree.heading("thickness", text="Thickness")
        self.results_tree.heading("r_value", text="R-Value")
        self.results_tree.heading("lca", text="LCA Impact")
        self.results_tree.heading("changed", text="Changed")
        
        # Define column widths
        self.results_tree.column("layer", width=60, anchor="center")
        self.results_tree.column("material", width=280, anchor="w")
        self.results_tree.column("thickness", width=100, anchor="center")
        self.results_tree.column("r_value", width=90, anchor="center")
        self.results_tree.column("lca", width=100, anchor="center")
        self.results_tree.column("changed", width=80, anchor="center")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        self.results_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Style for tags
        self.results_tree.tag_configure("changed", background="#d5f5d5")
        self.results_tree.tag_configure("total", background="#ecf0f1", font=("Segoe UI", 10, "bold"))
        
        # Bind double-click to edit
        self.results_tree.bind("<Double-1>", self._on_tree_double_click)
        
        # Edit instruction
        tk.Label(
            main,
            text="💡 Double-click a row or use the Edit buttons below to modify a layer",
            font=("Segoe UI", 9),
            bg="#f5f6fa",
            fg="#7f8c8d"
        ).pack(anchor="w", pady=(8, 0))
        
        # Edit buttons frame
        self.edit_buttons_frame = tk.Frame(main, bg="#f5f6fa")
        self.edit_buttons_frame.pack(fill="x", pady=(10, 0))
        
        # Bottom buttons
        btn_frame = tk.Frame(page, bg="#f5f6fa", pady=15, padx=25)
        btn_frame.pack(fill="x")
        
        ttk.Button(btn_frame, text="🔄 Re-Optimize", command=self._restart).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="💾 Save Report", command=self._save_report).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Exit", command=self.root.destroy).pack(side="left")
        
        # 'Go Back' / Reset changes button
        self.reset_btn = ttk.Button(btn_frame, text="↩️ Reset All Changes", command=self._reset_changes)
        self.reset_btn.pack(side="right")
    
    def _on_tree_double_click(self, event):
        """Handle double-click on tree row."""
        item = self.results_tree.selection()
        if item:
            item_id = item[0]
            try:
                layer_idx = int(item_id)
                self._edit_layer(layer_idx)
            except ValueError:
                pass  # Clicked on totals row
    
    def _refresh_results_page(self):
        """Refresh the results page with current data."""
        self._update_metrics_bar()
        self._refresh_layer_rows()
    
    def _update_metrics_bar(self):
        """Update the metrics cards."""
        for w in self.metrics_bar.winfo_children():
            w.destroy()
        
        total_r = sum(c.r_val for c in self.wall)
        total_lca = sum(c.lca_val for c in self.wall)
        u_value = 1.0 / (self.R_SI + total_r + self.R_SE)
        
        u_min = self.TARGET_U * (1 - self.TOLERANCE)
        u_max = self.TARGET_U * (1 + self.TOLERANCE)
        is_valid = u_min <= u_value <= u_max
        
        status_text = "✅ PASS" if is_valid else "❌ FAIL"
        status_color = "#27ae60" if is_valid else "#e74c3c"
        
        metrics_content = tk.Frame(self.metrics_bar, bg="#34495e")
        metrics_content.pack(fill="both", expand=True, padx=20, pady=12)
        
        metrics = [
            ("U-Value", f"{u_value:.4f}", "W/(m²K)", "#3498db"),
            ("Total LCA", f"{total_lca:.3f}", "kg CO₂-eq/m²", "#9b59b6"),
            ("Total R-Value", f"{total_r:.3f}", "m²K/W", "#e67e22"),
            ("Status", status_text, f"Target: {self.TARGET_U}", status_color)
        ]
        
        for label, value, unit, color in metrics:
            card = tk.Frame(metrics_content, bg=color, padx=15, pady=8)
            card.pack(side="left", padx=(0, 15))
            
            tk.Label(card, text=label, font=("Segoe UI", 9), bg=color, fg="#ecf0f1").pack(anchor="w")
            tk.Label(card, text=value, font=("Segoe UI", 16, "bold"), bg=color, fg="white").pack(anchor="w")
            tk.Label(card, text=unit, font=("Segoe UI", 8), bg=color, fg="#ecf0f1").pack(anchor="w")
    
    def _refresh_layer_rows(self):
        """Refresh the layer rows in the table."""
        # Clear existing items
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Clear edit buttons
        for w in self.edit_buttons_frame.winfo_children():
            w.destroy()
        
        tk.Label(
            self.edit_buttons_frame,
            text="Quick Edit:",
            font=("Segoe UI", 10),
            bg="#f5f6fa",
            fg="#2c3e50"
        ).pack(side="left", padx=(0, 10))
        
        # Add layer rows
        for i, c in enumerate(self.wall):
            # Check if changed from original
            orig = self.original_wall[i] if self.original_wall else None
            changed = orig and (c.material.name != orig.material.name or c.thickness != orig.thickness)
            
            change_text = "✓ Yes" if changed else "—"
            tags = ("changed",) if changed else ()
            
            self.results_tree.insert("", "end", iid=str(i), values=(
                f"L{i}",
                c.material.name[:40],
                f"{c.thickness*1000:.1f} mm",
                f"{c.r_val:.4f}",
                f"{c.lca_val:.4f}",
                change_text
            ), tags=tags)
            
            # Add quick edit button
            btn = ttk.Button(
                self.edit_buttons_frame,
                text=f"L{i}",
                width=4,
                command=lambda idx=i: self._edit_layer(idx)
            )
            btn.pack(side="left", padx=2)
        
        # Add totals row
        total_r = sum(c.r_val for c in self.wall)
        total_lca = sum(c.lca_val for c in self.wall)
        
        self.results_tree.insert("", "end", iid="total", values=(
            "TOTAL",
            "",
            "",
            f"{total_r:.4f}",
            f"{total_lca:.4f}",
            ""
        ), tags=("total",))
    
    # ==================== EDIT PAGE ====================
    
    def _create_edit_page(self):
        """Create the layer editing page."""
        page = tk.Frame(self.container, bg="#f5f6fa")
        self.pages["edit"] = page
        
        # Header
        header = tk.Frame(page, bg="#3498db", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        header_content = tk.Frame(header, bg="#3498db")
        header_content.pack(fill="both", expand=True, padx=20, pady=15)
        
        self.edit_title = tk.Label(
            header_content,
            text="🔧 Edit Layer 0",
            font=("Segoe UI", 16, "bold"),
            bg="#3498db",
            fg="white"
        )
        self.edit_title.pack(side="left")
        
        ttk.Button(header_content, text="← Back to Results", command=self._back_to_results).pack(side="right")
        
        # Main content
        main = tk.Frame(page, bg="#f5f6fa", padx=30, pady=20)
        main.pack(fill="both", expand=True)
        
        # Left: Current selection
        left = tk.LabelFrame(main, text=" Current Selection ", font=("Segoe UI", 11, "bold"), bg="#f5f6fa", padx=15, pady=15)
        left.pack(side="left", fill="y", padx=(0, 20))
        
        self.current_material_lbl = tk.Label(left, text="Material: —", font=("Segoe UI", 11), bg="#f5f6fa", anchor="w", wraplength=200)
        self.current_material_lbl.pack(anchor="w", pady=5)
        
        self.current_thickness_lbl = tk.Label(left, text="Thickness: —", font=("Segoe UI", 11), bg="#f5f6fa", anchor="w")
        self.current_thickness_lbl.pack(anchor="w", pady=5)
        
        self.current_r_lbl = tk.Label(left, text="R-Value: —", font=("Segoe UI", 11), bg="#f5f6fa", anchor="w")
        self.current_r_lbl.pack(anchor="w", pady=5)
        
        self.current_lca_lbl = tk.Label(left, text="LCA: —", font=("Segoe UI", 11), bg="#f5f6fa", anchor="w")
        self.current_lca_lbl.pack(anchor="w", pady=5)
        
        # Preview (what will change)
        preview_frame = tk.LabelFrame(left, text=" Preview After Change ", font=("Segoe UI", 10), bg="#f5f6fa", padx=10, pady=10)
        preview_frame.pack(fill="x", pady=(20, 0))
        
        self.preview_material = tk.Label(preview_frame, text="Select an option →", font=("Segoe UI", 10), bg="#f5f6fa", fg="#7f8c8d", wraplength=180)
        self.preview_material.pack(anchor="w")
        
        self.preview_values = tk.Label(preview_frame, text="", font=("Segoe UI", 10), bg="#f5f6fa", fg="#27ae60")
        self.preview_values.pack(anchor="w", pady=(5, 0))
        
        # Right: Options list
        right = tk.LabelFrame(main, text=" Available Options — Select one ", font=("Segoe UI", 11, "bold"), bg="#f5f6fa", padx=15, pady=15)
        right.pack(side="left", fill="both", expand=True)
        
        # Options treeview
        cols = ("material", "thickness", "r_val", "lca")
        self.options_tree = ttk.Treeview(right, columns=cols, show="headings", height=15)
        
        self.options_tree.heading("material", text="Material")
        self.options_tree.heading("thickness", text="Thickness")
        self.options_tree.heading("r_val", text="R-Value")
        self.options_tree.heading("lca", text="LCA")
        
        self.options_tree.column("material", width=250)
        self.options_tree.column("thickness", width=90, anchor="center")
        self.options_tree.column("r_val", width=80, anchor="center")
        self.options_tree.column("lca", width=80, anchor="center")
        
        scroll = ttk.Scrollbar(right, orient="vertical", command=self.options_tree.yview)
        self.options_tree.configure(yscrollcommand=scroll.set)
        
        self.options_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        
        # Bind selection
        self.options_tree.bind("<<TreeviewSelect>>", self._on_option_select)
        
        # Bottom buttons
        btn_frame = tk.Frame(page, bg="#f5f6fa", pady=15, padx=30)
        btn_frame.pack(fill="x")
        
        self.apply_btn = ttk.Button(btn_frame, text="✓ Apply This Selection", command=self._apply_selection, state="disabled")
        self.apply_btn.pack(side="left", padx=(0, 10))
        
        ttk.Button(btn_frame, text="✗ Cancel", command=self._back_to_results).pack(side="left")
        
        # Store data
        self.edit_layer_idx = None
        self.edit_options = []
    
    def _edit_layer(self, layer_idx: int):
        """Open the edit page for a layer."""
        self.edit_layer_idx = layer_idx
        
        # Update title
        self.edit_title.configure(text=f"🔧 Edit Layer {layer_idx}")
        
        # Current values
        current = self.wall[layer_idx]
        self.current_material_lbl.configure(text=f"Material: {current.material.name[:30]}")
        self.current_thickness_lbl.configure(text=f"Thickness: {current.thickness*1000:.1f} mm")
        self.current_r_lbl.configure(text=f"R-Value: {current.r_val:.4f} m²K/W")
        self.current_lca_lbl.configure(text=f"LCA: {current.lca_val:.4f} kg CO₂-eq/m²")
        
        # Reset preview
        self.preview_material.configure(text="Select an option →", fg="#7f8c8d")
        self.preview_values.configure(text="")
        
        # Populate options
        self.edit_options = []
        for item in self.options_tree.get_children():
            self.options_tree.delete(item)
        
        valid_materials = [m for m in self.materials if m.layer_index == layer_idx]
        
        for mat in valid_materials:
            for thickness in mat.thickness_options:
                r_val = self.calc_r(mat, thickness)
                lca_val = self.calc_lca(mat, thickness)
                candidate = self.Candidate(mat, thickness, r_val, lca_val)
                self.edit_options.append(candidate)
                
                self.options_tree.insert("", "end", values=(
                    mat.name[:35],
                    f"{thickness*1000:.1f} mm",
                    f"{r_val:.4f}",
                    f"{lca_val:.4f}"
                ), iid=str(len(self.edit_options) - 1))
        
        self.apply_btn.configure(state="disabled")
        self._show_page("edit")
    
    def _on_option_select(self, event):
        """Handle option selection - show preview."""
        sel = self.options_tree.selection()
        if sel:
            idx = int(sel[0])
            opt = self.edit_options[idx]
            
            # Update preview
            self.preview_material.configure(text=f"→ {opt.material.name[:25]}", fg="#2c3e50")
            self.preview_values.configure(
                text=f"Thickness: {opt.thickness*1000:.1f} mm\n"
                     f"R-Value: {opt.r_val:.4f}\n"
                     f"LCA: {opt.lca_val:.4f}"
            )
            
            self.apply_btn.configure(state="normal")
    
    def _apply_selection(self):
        """Apply the selected option."""
        sel = self.options_tree.selection()
        if sel:
            idx = int(sel[0])
            self.wall[self.edit_layer_idx] = self.edit_options[idx]
            
            # Show confirmation
            messagebox.showinfo(
                "Layer Updated",
                f"✅ Layer {self.edit_layer_idx} has been updated!\n\n"
                f"New Material: {self.edit_options[idx].material.name[:30]}\n"
                f"New Thickness: {self.edit_options[idx].thickness*1000:.1f} mm"
            )
            
            self._back_to_results()
    
    def _back_to_results(self):
        """Go back to results page."""
        self._refresh_results_page()
        self._show_page("results")
    
    # ==================== ACTIONS ====================
    
    def _save_report(self):
        """Save current wall report."""
        try:
            from main import save_results
            raw_file, report_file = save_results(self.wall)
            messagebox.showinfo(
                "Report Saved",
                f"✅ Report saved successfully!\n\n"
                f"📄 {report_file.name}\n"
                f"📁 Location: outputs/reports/"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save:\n{e}")
    
    def _reset_changes(self):
        """Reset all changes to original optimization result."""
        if self.original_wall:
            if messagebox.askyesno("Reset Changes", "Reset all layers to the original optimization result?"):
                self.wall = [
                    self.Candidate(c.material, c.thickness, c.r_val, c.lca_val)
                    for c in self.original_wall
                ]
                self._refresh_results_page()
                messagebox.showinfo("Reset", "✅ All layers reset to original values!")
    
    def _restart(self):
        """Restart optimization."""
        if messagebox.askyesno("Re-Optimize", "Run a fresh optimization? This will reset all changes."):
            # Reset steps
            for lbl, status in self.step_widgets:
                lbl.configure(fg="#7f8c8d")
                status.configure(text="○", fg="#7f8c8d")
            self.progress_bar["value"] = 0
            
            self._show_page("progress")
            self.root.after(300, self.run_optimization)
    
    def run(self):
        """Start the application."""
        self.root.after(500, self.run_optimization)
        self.root.mainloop()


def main():
    """Entry point."""
    app = WallOptimizerApp()
    app.run()


if __name__ == "__main__":
    main()
