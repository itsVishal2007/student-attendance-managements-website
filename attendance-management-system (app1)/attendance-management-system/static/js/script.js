// script.js
// Client-side UI/UX enhancements for the Attendance Management System.
// NOTE: purely presentational/frontend behaviour — no data, routes, or
// business logic are touched here.

function confirmDelete(name) {
    return confirm(`Are you sure you want to delete "${name}"? This action cannot be undone.`);
}

document.addEventListener("DOMContentLoaded", function () {

    /* ---------------------------------------------------------------
       Auto-dismiss flash messages
    --------------------------------------------------------------- */
    const flashes = document.querySelectorAll(".flash");
    flashes.forEach((el) => {
        setTimeout(() => {
            el.style.transition = "opacity 0.5s ease, transform 0.5s ease";
            el.style.opacity = "0";
            el.style.transform = "translateY(-6px)";
            setTimeout(() => el.remove(), 500);
        }, 4500);
    });

    /* ---------------------------------------------------------------
       Sidebar drawer (mobile)
    --------------------------------------------------------------- */
    const sidebar = document.querySelector(".sidebar");
    const backdrop = document.querySelector(".sidebar-backdrop");
    const menuToggle = document.querySelector(".menu-toggle");

    function openSidebar() {
        if (!sidebar) return;
        sidebar.classList.add("open");
        backdrop?.classList.add("show");
    }
    function closeSidebar() {
        if (!sidebar) return;
        sidebar.classList.remove("open");
        backdrop?.classList.remove("show");
    }
    menuToggle?.addEventListener("click", () => {
        sidebar?.classList.contains("open") ? closeSidebar() : openSidebar();
    });
    backdrop?.addEventListener("click", closeSidebar);
    document.querySelectorAll(".sidebar-link").forEach((l) => l.addEventListener("click", closeSidebar));

    /* ---------------------------------------------------------------
       Ripple effect on buttons
    --------------------------------------------------------------- */
    document.querySelectorAll(".btn").forEach((btn) => {
        btn.addEventListener("click", function (e) {
            const rect = btn.getBoundingClientRect();
            const ripple = document.createElement("span");
            const size = Math.max(rect.width, rect.height);
            ripple.className = "ripple";
            ripple.style.width = ripple.style.height = size + "px";
            ripple.style.left = (e.clientX - rect.left - size / 2) + "px";
            ripple.style.top = (e.clientY - rect.top - size / 2) + "px";
            btn.appendChild(ripple);
            setTimeout(() => ripple.remove(), 600);
        });
    });

    /* ---------------------------------------------------------------
       Scroll-reveal animation
    --------------------------------------------------------------- */
    const revealEls = document.querySelectorAll(".reveal");
    if ("IntersectionObserver" in window && revealEls.length) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("in-view");
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });
        revealEls.forEach((el) => observer.observe(el));
    } else {
        revealEls.forEach((el) => el.classList.add("in-view"));
    }

    /* ---------------------------------------------------------------
       Animated stat counters (card-value with data-count)
    --------------------------------------------------------------- */
    document.querySelectorAll("[data-count]").forEach((el) => {
        const target = parseFloat(el.dataset.count);
        if (isNaN(target)) return;
        const suffix = el.dataset.suffix || "";
        const duration = 900;
        const start = performance.now();
        function tick(now) {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const value = target * eased;
            el.textContent = (Number.isInteger(target) ? Math.round(value) : value.toFixed(1)) + suffix;
            if (progress < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    });

    /* ---------------------------------------------------------------
       Animate attendance rings / progress bars from 0 -> --pct
    --------------------------------------------------------------- */
    document.querySelectorAll(".attendance-ring[data-pct]").forEach((ring) => {
        const pct = parseFloat(ring.dataset.pct) || 0;
        ring.style.setProperty("--pct", 0);
        requestAnimationFrame(() => {
            setTimeout(() => {
                ring.style.transition = "--pct 1.1s ease";
                ring.animate(
                    [{ "--pct": 0 }, { "--pct": pct }],
                    { duration: 1100, easing: "cubic-bezier(.4,0,.2,1)", fill: "forwards" }
                );
                // Fallback for engines without animatable custom props in @property:
                let startTs = null;
                function step(ts) {
                    if (!startTs) startTs = ts;
                    const p = Math.min((ts - startTs) / 1100, 1);
                    const eased = 1 - Math.pow(1 - p, 3);
                    ring.style.setProperty("--pct", (pct * eased).toFixed(1));
                    if (p < 1) requestAnimationFrame(step);
                }
                requestAnimationFrame(step);
            }, 80);
        });
    });

    document.querySelectorAll(".progress-fill[data-width]").forEach((bar) => {
        const w = bar.dataset.width;
        requestAnimationFrame(() => {
            setTimeout(() => { bar.style.width = w + "%"; }, 120);
        });
    });

    /* ---------------------------------------------------------------
       Highlight current weekday in the Timetable grid (frontend-only;
       uses the browser's local date, no server data involved)
    --------------------------------------------------------------- */
    const dayHeaders = document.querySelectorAll(".tt-day");
    if (dayHeaders.length) {
        const todayName = new Date().toLocaleDateString("en-US", { weekday: "long" });
        dayHeaders.forEach((th) => {
            if (th.textContent.trim() === todayName) {
                th.closest("tr")?.classList.add("tt-today-row");
            }
        });
    }

    /* ---------------------------------------------------------------
       Smooth "selection" feedback on attendance chips
    --------------------------------------------------------------- */
    document.querySelectorAll(".status-radio-group input[type='radio']").forEach((input) => {
        input.addEventListener("change", () => {
            const label = input.closest("label");
            if (!label) return;
            label.animate(
                [{ transform: "scale(0.94)" }, { transform: "scale(1)" }],
                { duration: 220, easing: "cubic-bezier(.4,0,.2,1)" }
            );
        });
    });
});
