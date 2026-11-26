/* Alpine component backing templates/components/line_formset.html */
document.addEventListener("alpine:init", () => {
    window.Alpine.data("lineFormset", (prefix) => ({
        prefix,
        deleted: {},
        total: 0,
        hasTotals: false,
        init() {
            this.$el.addEventListener("input", () => this.recalc());
            this.$el.addEventListener("change", () => this.recalc());
        },
        totalForms() {
            return this.$root.querySelector(`input[name="${this.prefix}-TOTAL_FORMS"]`);
        },
        addRow() {
            const total = this.totalForms();
            const index = parseInt(total.value, 10);
            const html = this.$refs.tpl.innerHTML.replace(/__prefix__/g, index);
            this.$refs.rows.insertAdjacentHTML("beforeend", html);
            total.value = index + 1;
            const row = this.$refs.rows.lastElementChild;
            const first = row.querySelector("select, input:not([type=hidden])");
            if (first) first.focus();
            this.recalc();
        },
        removeRow(evt) {
            // An untouched extra form is ignored by Django, so clearing + hiding is enough.
            const row = evt.target.closest("tr");
            row.querySelectorAll("input:not([type=hidden]), select, textarea").forEach((el) => { el.value = ""; });
            row.classList.add("hidden");
            this.recalc();
        },
        toggleDelete(index, evt) {
            const row = evt.target.closest("tr");
            const box = row.querySelector(`input[name="${this.prefix}-${index}-DELETE"]`);
            if (box) box.checked = !box.checked;
            this.deleted[index] = box ? box.checked : false;
            this.recalc();
        },
        recalc() {
            let sum = 0;
            let any = false;
            this.$refs.rows.querySelectorAll("tr[data-row]").forEach((row) => {
                const q = row.querySelector('input[name$="-quantity"]');
                const p = row.querySelector('input[name$="-unit_price"]');
                const cell = row.querySelector("[data-amount]");
                if (!q || !p) return;
                any = true;
                const del = row.querySelector('input[name$="-DELETE"]');
                const amount = (parseFloat(q.value) || 0) * (parseFloat(p.value) || 0);
                if (cell) cell.textContent = amount ? this.formatMoney(amount) : "—";
                if (!row.classList.contains("hidden") && !(del && del.checked)) sum += amount;
            });
            this.hasTotals = any;
            this.total = sum;
        },
        formatMoney(v) {
            return "₹" + Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        },
    }));
});
