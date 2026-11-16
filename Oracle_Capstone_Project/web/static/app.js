/**
 * Oracle Financial Period Close Agent — Frontend Application
 * IBM Consulting Advantage Enterprise Web Interface
 */

document.addEventListener("DOMContentLoaded", () => {
    // App State
    const state = {
        activeTab: "tab-chat",
        period: "Dec-24",
        scenario: "default",
        mode: "MOCK", // MOCK or REAL
        ledgers: {},
        blockers: [],
        templates: [],
        isProcessing: false,
    };

    // DOM Elements
    const elements = {
        navTabs: document.querySelectorAll(".nav-tab"),
        tabPanels: document.querySelectorAll(".tab-panel"),
        periodSelector: document.getElementById("period-selector"),
        scenarioSelector: document.getElementById("scenario-selector"),
        btnRefresh: document.getElementById("btn-refresh-state"),
        connectionPill: document.getElementById("connection-pill"),
        connectionModeText: document.getElementById("connection-mode-text"),
        navBlockedBadge: document.getElementById("nav-blocked-badge"),
        blockerCountBadge: document.getElementById("blocker-count-badge"),

        // Close Request Form Tab
        closeRequestForm: document.getElementById("close-request-form"),
        crfEnvironment: document.getElementById("crf-environment"),
        crfLedger: document.getElementById("crf-ledger"),
        crfPeriod: document.getElementById("crf-period"),
        crfAction: document.getElementById("crf-action"),
        btnSubmitCloseRequest: document.getElementById("btn-submit-close-request"),
        btnClearResults: document.getElementById("btn-clear-results"),
        crfProcessingHint: document.getElementById("crf-processing-hint"),
        closeResultsPanel: document.getElementById("close-results-panel"),
        closeIdleState: document.getElementById("close-idle-state"),
        resultsHeading: document.getElementById("results-heading"),
        resultsMetaLabel: document.getElementById("results-meta-label"),
        resultsOverallBadge: document.getElementById("results-overall-badge"),
        resultsLedgersContainer: document.getElementById("results-ledgers-container"),
        promptTemplatesList: document.getElementById("prompt-templates-list"),

        // Dashboard Tab
        kpiTotalLedgers: document.getElementById("kpi-total-ledgers"),
        kpiReadinessState: document.getElementById("kpi-readiness-state"),
        kpiReadinessDesc: document.getElementById("kpi-readiness-desc"),
        kpiStatusIcon: document.getElementById("kpi-status-icon"),
        kpiBlockerCount: document.getElementById("kpi-blocker-count"),
        orchPeriodText: document.getElementById("orch-period-text"),
        matrixPeriodLabel: document.getElementById("matrix-period-label"),
        btnRunAssessment: document.getElementById("btn-run-assessment"),
        btnExecuteClose: document.getElementById("btn-execute-close"),
        ledgerCardsContainer: document.getElementById("ledger-cards-container"),
        moduleMatrixTbody: document.getElementById("module-matrix-tbody"),

        // Blockers Tab
        blockersTable: document.getElementById("blockers-table"),
        blockersTbody: document.getElementById("blockers-tbody"),
        noBlockersMessage: document.getElementById("no-blockers-message"),
        blockerSearchInput: document.getElementById("blocker-search-input"),
        blockerModuleFilter: document.getElementById("blocker-module-filter"),

        // Testing Tab
        btnRunTestPack: document.getElementById("btn-run-test-pack"),
        btnRunUnitTests: document.getElementById("btn-run-unit-tests"),
        testTerminalOutput: document.getElementById("test-terminal-output"),
        testPackStatsBanner: document.getElementById("test-pack-stats-banner"),

        // Config Tab
        configForm: document.getElementById("config-form"),
        cfgMode: document.getElementById("cfg-mode"),
        cfgUrl: document.getElementById("cfg-url"),
        cfgUsername: document.getElementById("cfg-username"),
        cfgPassword: document.getElementById("cfg-password"),
        btnTestConnection: document.getElementById("btn-test-connection"),
        configStatusAlert: document.getElementById("config-status-alert"),

        // Modals
        resolutionModal: document.getElementById("resolution-modal"),
        modalTitle: document.getElementById("modal-title"),
        modalBodyContent: document.getElementById("modal-body-content"),
        btnCloseModal: document.getElementById("btn-close-modal"),
        btnModalDismiss: document.getElementById("btn-modal-dismiss"),

        closeConfirmModal: document.getElementById("close-confirm-modal"),
        confirmPeriodText: document.getElementById("confirm-period-text"),
        btnCloseConfirmModal: document.getElementById("btn-close-confirm-modal"),
        btnCancelClose: document.getElementById("btn-cancel-close"),
        btnConfirmExecuteClose: document.getElementById("btn-confirm-execute-close"),
    };

    // =========================================================================
    // INITIALIZATION
    // =========================================================================

    async function init() {
        setupEventListeners();
        await loadPromptTemplates();
        await fetchSystemStatus();
        await refreshReadinessAssessment();
    }

    // =========================================================================
    // EVENT LISTENERS
    // =========================================================================

    function setupEventListeners() {
        // Tab switching
        elements.navTabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                const targetTab = tab.getAttribute("data-tab");
                switchTab(targetTab);
            });
        });

        // Period & Scenario Change
        elements.periodSelector.addEventListener("change", (e) => {
            state.period = e.target.value;
            elements.orchPeriodText.textContent = state.period;
            elements.matrixPeriodLabel.textContent = state.period;
            elements.confirmPeriodText.textContent = state.period;
            refreshReadinessAssessment();
        });

        elements.scenarioSelector.addEventListener("change", async (e) => {
            state.scenario = e.target.value;
            await switchScenario(state.scenario);
        });

        elements.btnRefresh.addEventListener("click", () => {
            fetchSystemStatus();
            refreshReadinessAssessment();
        });

        // Close Request Form
        elements.closeRequestForm.addEventListener("submit", (e) => {
            e.preventDefault();
            submitCloseRequest();
        });

        elements.btnClearResults.addEventListener("click", () => {
            elements.closeResultsPanel.style.display = "none";
            elements.closeIdleState.style.display = "flex";
        });

        // Dashboard Actions
        elements.btnRunAssessment.addEventListener("click", () => {
            refreshReadinessAssessment(true);
        });

        elements.btnExecuteClose.addEventListener("click", () => {
            elements.confirmPeriodText.textContent = state.period;
            elements.closeConfirmModal.style.display = "flex";
        });

        elements.btnCloseConfirmModal.addEventListener("click", () => {
            elements.closeConfirmModal.style.display = "none";
        });

        elements.btnCancelClose.addEventListener("click", () => {
            elements.closeConfirmModal.style.display = "none";
        });

        elements.btnConfirmExecuteClose.addEventListener("click", async () => {
            elements.closeConfirmModal.style.display = "none";
            await executeFinancialClose();
        });

        // Blocker Filters
        elements.blockerSearchInput.addEventListener("input", filterBlockersTable);
        elements.blockerModuleFilter.addEventListener("change", filterBlockersTable);

        // Modals
        elements.btnCloseModal.addEventListener("click", closeModal);
        elements.btnModalDismiss.addEventListener("click", closeModal);
        elements.resolutionModal.addEventListener("click", (e) => {
            if (e.target === elements.resolutionModal) closeModal();
        });

        // Testing Actions
        elements.btnRunTestPack.addEventListener("click", run8CaseTestPack);
        elements.btnRunUnitTests.addEventListener("click", runUnitTests);

        // Config Form
        elements.configForm.addEventListener("submit", saveConfiguration);
        elements.btnTestConnection.addEventListener("click", testConnection);
    }

    // =========================================================================
    // TAB MANAGEMENT
    // =========================================================================

    function switchTab(tabId) {
        state.activeTab = tabId;
        elements.navTabs.forEach((tab) => {
            if (tab.getAttribute("data-tab") === tabId) {
                tab.classList.add("active");
            } else {
                tab.classList.remove("active");
            }
        });

        elements.tabPanels.forEach((panel) => {
            if (panel.id === tabId) {
                panel.classList.add("active");
            } else {
                panel.classList.remove("active");
            }
        });
    }

    // =========================================================================
    // API CALLS & DATA FETCHING
    // =========================================================================

    async function fetchSystemStatus() {
        try {
            const res = await fetch(`/api/status?period=${encodeURIComponent(state.period)}`);
            const data = await res.json();
            if (data && data.status === "SUCCESS") {
                state.mode = data.mode || "MOCK";
                state.scenario = data.scenario || "default";
                elements.scenarioSelector.value = state.scenario;
                updateConnectionIndicator(state.mode);
            }
        } catch (err) {
            console.error("Failed to fetch status:", err);
        }
    }

    async function switchScenario(scenarioName) {
        try {
            const res = await fetch("/api/scenario", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ scenario: scenarioName }),
            });
            const data = await res.json();
            if (data.status === "SUCCESS") {
                await refreshReadinessAssessment();
                console.info(`Scenario switched to: ${data.scenario_title || scenarioName}`);
            }
        } catch (err) {
            console.error("Error switching scenario:", err);
        }
    }

    async function refreshReadinessAssessment(showChatMessage = false) {
        try {
            const res = await fetch("/api/assessment", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ period: state.period }),
            });
            const result = await res.json();
            if (result.status === "SUCCESS") {
                const readiness = result.data;
                updateDashboard(readiness);
                updateBlockersHub(readiness);

                if (showChatMessage) {
                    // Switch to form tab and show results
                    switchTab("tab-chat");
                    renderCloseResults(readiness, state.period, "readiness", readiness.overall_ready ? "READY" : "BLOCKED");
                }
            }
        } catch (err) {
            console.error("Assessment fetch error:", err);
        }
    }

    async function executeFinancialClose() {
        // Pre-fill the form and run as a close request, then switch to it
        switchTab("tab-chat");
        if (elements.crfPeriod) elements.crfPeriod.value = state.period;
        if (elements.crfAction) elements.crfAction.value = "close";
        if (elements.crfLedger) elements.crfLedger.value = "all";
        await submitCloseRequest();
    }

    // =========================================================================
    // CLOSE REQUEST FORM — SUBMISSION & RESULTS RENDERING
    // =========================================================================

    async function submitCloseRequest() {
        if (state.isProcessing) return;
        state.isProcessing = true;

        const ledgerVal = elements.crfLedger.value;
        const period    = elements.crfPeriod.value;
        const action    = elements.crfAction.value;
        const ledgerId  = ledgerVal === "all" ? null : ledgerVal;

        // Keep global period in sync
        state.period = period;

        // Show processing hint, hide results
        elements.crfProcessingHint.style.display = "inline-flex";
        elements.btnSubmitCloseRequest.disabled = true;
        elements.closeResultsPanel.style.display = "none";
        elements.closeIdleState.style.display = "none";

        try {
            let data;
            if (action === "close") {
                const res = await fetch("/api/close", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ period, ledger_id: ledgerId }),
                });
                data = await res.json();
                // /api/close returns { reply, data: close_result } — we re-fetch readiness for the subledger table
                const rdRes = await fetch("/api/assessment", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ period, ledger_id: ledgerId }),
                });
                const rdData = await rdRes.json();
                if (rdData.status === "SUCCESS") {
                    renderCloseResults(rdData.data, period, action, data.overall_status || (rdData.data.overall_ready ? "COMPLETED" : "BLOCKED"));
                    updateDashboard(rdData.data);
                    updateBlockersHub(rdData.data);
                }
            } else {
                // Readiness check or Status Inquiry — use /api/assessment
                const res = await fetch("/api/assessment", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ period, ledger_id: ledgerId }),
                });
                data = await res.json();
                if (data.status === "SUCCESS") {
                    renderCloseResults(data.data, period, action, data.data.overall_ready ? "READY" : "BLOCKED");
                    updateDashboard(data.data);
                    updateBlockersHub(data.data);
                }
            }
        } catch (err) {
            elements.closeIdleState.style.display = "flex";
            elements.closeIdleState.querySelector(".idle-text").textContent =
                "❌ Error communicating with Period Close Agent: " + err.message;
        } finally {
            elements.crfProcessingHint.style.display = "none";
            elements.btnSubmitCloseRequest.disabled = false;
            state.isProcessing = false;
        }
    }

    function renderCloseResults(readiness, period, action, overallStatus) {
        const report = readiness.ledgers_report || {};
        const isReady = readiness.overall_ready;
        const totalBlockers = readiness.total_blockers || 0;

        // Heading
        const actionLabels = { readiness: "Readiness Check", close: "Close Request", status: "Status Inquiry" };
        elements.resultsHeading.textContent = `${actionLabels[action] || "Results"} — ${period}`;
        elements.resultsMetaLabel.textContent =
            `${Object.keys(report).length} ledger(s) assessed • ${totalBlockers} blocker(s) found`;

        // Overall badge
        let badgeHtml;
        if (overallStatus === "COMPLETED") {
            badgeHtml = `<span class="results-badge results-badge-success">✓ CLOSED</span>`;
        } else if (isReady || overallStatus === "READY") {
            badgeHtml = `<span class="results-badge results-badge-success">✓ READY</span>`;
        } else {
            badgeHtml = `<span class="results-badge results-badge-blocked">✗ BLOCKED</span>`;
        }
        elements.resultsOverallBadge.innerHTML = badgeHtml;

        // Per-ledger subledger tables
        elements.resultsLedgersContainer.innerHTML = "";

        const MODULES = [
            { key: "costing",   label: "Cost Management" },
            { key: "sla",       label: "Subledger SLA" },
            { key: "ap",        label: "Payables (AP)" },
            { key: "ar",        label: "Receivables (AR)" },
            { key: "inventory", label: "Inventory" },
        ];

        Object.entries(report).forEach(([ledgerName, ldata]) => {
            const checks = ldata.module_checks || {};
            const ledgerReady = ldata.readiness_status === "READY";

            const ledgerBlock = document.createElement("div");
            ledgerBlock.className = "results-ledger-block";

            // Build rows for each subledger module
            const rows = MODULES.map((mod) => {
                const check = checks[mod.key] || { status: "PASS", blockers: [] };
                const canClose = check.status === "PASS";

                // Collect reasons from blockers
                let reason = "No blockers";
                if (!canClose && check.blockers && check.blockers.length > 0) {
                    reason = check.blockers.map(b => b.error_message || b.description || "Blocker found").join("; ");
                }

                return `
                    <tr class="results-row ${canClose ? "row-pass" : "row-fail"}">
                        <td class="results-module-cell">${escapeHtml(mod.label)}</td>
                        <td class="results-status-cell">
                            ${canClose
                                ? `<span class="result-icon result-pass" title="Can be closed">✓</span>`
                                : `<span class="result-icon result-fail" title="Blocked">✗</span>`}
                        </td>
                        <td class="results-reason-cell ${canClose ? "reason-clear" : "reason-blocked"}">
                            ${canClose ? "No blockers" : escapeHtml(reason)}
                        </td>
                    </tr>
                `;
            }).join("");

            const ledgerStatusClass = ledgerReady ? "ledger-block-ready" : "ledger-block-blocked";
            const ledgerStatusIcon  = ledgerReady ? "✓" : "✗";
            const ledgerStatusText  = ledgerReady ? "Ready to Close" : "Blocked";

            ledgerBlock.innerHTML = `
                <div class="results-ledger-header ${ledgerStatusClass}">
                    <span class="results-ledger-title">${escapeHtml(ledgerName)}</span>
                    <span class="results-ledger-id">ID: ${ldata.ledger_id} | ${ldata.currency}</span>
                    <span class="results-ledger-status">
                        <span class="result-icon ${ledgerReady ? "result-pass" : "result-fail"}">${ledgerStatusIcon}</span>
                        ${ledgerStatusText}
                    </span>
                </div>
                <table class="results-subledger-table">
                    <thead>
                        <tr>
                            <th>Subledger / Module</th>
                            <th>Can Close?</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `;

            elements.resultsLedgersContainer.appendChild(ledgerBlock);
        });

        elements.closeIdleState.style.display = "none";
        elements.closeResultsPanel.style.display = "block";
    }

    // =========================================================================
    // PROMPT TEMPLATES LOADER (From agent_prompt_inputs.txt)
    // =========================================================================

    async function loadPromptTemplates() {
        try {
            const res = await fetch("/api/prompts");
            const data = await res.json();
            if (data && data.templates) {
                state.templates = data.templates;
                renderPromptTemplatesList(data.templates);
            }
        } catch (err) {
            console.error("Failed to load prompt templates:", err);
        }
    }

    function renderPromptTemplatesList(templates) {
        elements.promptTemplatesList.innerHTML = "";
        templates.forEach((t) => {
            const card = document.createElement("div");
            card.className = "prompt-template-card";
            card.innerHTML = `
                <div class="template-card-title">${t.id}: ${t.title}</div>
                <span class="template-card-badge ${t.badgeClass}">${t.badge}</span>
                <div class="template-card-desc">${t.description}</div>
            `;
            card.addEventListener("click", () => {
                document.querySelectorAll(".prompt-template-card").forEach((c) => c.classList.remove("active"));
                card.classList.add("active");

                // Parse the prompt text and fill the form fields
                const prompt = t.prompt || "";

                // Extract Period (e.g. "Oct-24", "Nov-24", "Dec-24", "Jan-25")
                const periodMatch = prompt.match(/Period\s*:\s*([A-Za-z]{3}-\d{2})/i);
                if (periodMatch) {
                    const p = periodMatch[1];
                    const opt = elements.crfPeriod.querySelector(`option[value="${p}"]`);
                    if (opt) elements.crfPeriod.value = p;
                }

                // Extract Ledger ID (1001 / 1002 / 1003) or multi-ledger
                if (/1003/.test(prompt)) {
                    elements.crfLedger.value = "1003";
                } else if (/1002/.test(prompt)) {
                    elements.crfLedger.value = "1002";
                } else if (/1001/.test(prompt)) {
                    elements.crfLedger.value = "1001";
                } else if (/global ledger set|all three|all ledgers/i.test(prompt)) {
                    elements.crfLedger.value = "all";
                }

                // Extract Action
                if (/close request/i.test(prompt)) {
                    elements.crfAction.value = "close";
                } else if (/readiness check|readiness assessment/i.test(prompt)) {
                    elements.crfAction.value = "readiness";
                } else if (/status inquiry/i.test(prompt)) {
                    elements.crfAction.value = "status";
                }
            });
            elements.promptTemplatesList.appendChild(card);
        });
    }

    // =========================================================================
    // DASHBOARD RENDERING
    // =========================================================================

    function updateDashboard(readiness) {
        const report = readiness.ledgers_report || {};
        const isReady = readiness.overall_ready;
        const totalBlockers = readiness.total_blockers || 0;
        const totalLedgers = Object.keys(report).length;

        elements.kpiTotalLedgers.textContent = totalLedgers;
        elements.kpiBlockerCount.textContent = totalBlockers;

        if (isReady) {
            elements.kpiReadinessState.textContent = "READY";
            elements.kpiReadinessState.style.color = "var(--status-success)";
            elements.kpiReadinessDesc.textContent = "All checks passed cleanly";
            elements.kpiStatusIcon.textContent = "✅";
            elements.navBlockedBadge.style.display = "none";
        } else {
            elements.kpiReadinessState.textContent = "HOLD";
            elements.kpiReadinessState.style.color = "var(--status-danger)";
            elements.kpiReadinessDesc.textContent = `${totalBlockers} active blocker(s) detected`;
            elements.kpiStatusIcon.textContent = "⚠️";
            elements.navBlockedBadge.style.display = "inline-block";
        }

        elements.blockerCountBadge.textContent = totalBlockers;

        // Render Ledger Cards
        renderLedgerCards(report);

        // Render Matrix Table
        renderMatrixTable(report);
    }

    function renderLedgerCards(report) {
        elements.ledgerCardsContainer.innerHTML = "";

        Object.entries(report).forEach(([ledgerName, data]) => {
            const card = document.createElement("div");
            card.className = "ledger-card";

            const isBlocked = data.readiness_status === "BLOCKED";
            const isClosed = data.costing_status === "Closed" && data.gl_status === "Closed";

            let tagClass = "tag-ready";
            let tagText = "READY";
            if (isClosed) {
                tagClass = "tag-closed";
                tagText = "CLOSED";
            } else if (isBlocked) {
                tagClass = "tag-blocked";
                tagText = "HOLD / BLOCKED";
            }

            let blockersHtml = "";
            if (data.blockers && data.blockers.length > 0) {
                const itemsList = data.blockers
                    .slice(0, 2)
                    .map((b) => `<li>${escapeHtml(b)}</li>`)
                    .join("");
                blockersHtml = `
                    <div class="ledger-blockers-summary">
                        <div class="title">🚨 Blockers Detected (${data.blockers.length}):</div>
                        <ul>${itemsList}</ul>
                    </div>
                `;
            }

            card.innerHTML = `
                <div class="ledger-card-header">
                    <div class="ledger-card-title-group">
                        <h3>${ledgerName}</h3>
                        <span class="meta">ID: ${data.ledger_id} | ${data.currency} | ${data.chart_of_accounts || "COA"}</span>
                    </div>
                    <span class="ledger-status-tag ${tagClass}">${tagText}</span>
                </div>
                <div class="ledger-card-body">
                    <div class="period-status-row">
                        <span class="label">Costing Period:</span>
                        <span class="value ${data.costing_status === "Closed" ? "closed" : "open"}">${data.costing_status}</span>
                    </div>
                    <div class="period-status-row">
                        <span class="label">General Ledger Period:</span>
                        <span class="value ${data.gl_status === "Closed" ? "closed" : "open"}">${data.gl_status}</span>
                    </div>
                    ${blockersHtml}
                </div>
            `;
            elements.ledgerCardsContainer.appendChild(card);
        });
    }

    function renderMatrixTable(report) {
        elements.moduleMatrixTbody.innerHTML = "";

        Object.entries(report).forEach(([ledgerName, data]) => {
            const checks = data.module_checks || {};
            const tr = document.createElement("tr");

            const costStat = checks.costing?.status || "PASS";
            const slaStat = checks.sla?.status || "PASS";
            const apStat = checks.ap?.status || "PASS";
            const arStat = checks.ar?.status || "PASS";
            const invStat = checks.inventory?.status || "PASS";

            tr.innerHTML = `
                <td><strong>${ledgerName}</strong> <small style="color:#888;">(${data.ledger_id})</small></td>
                <td><span class="${costStat === 'PASS' ? 'badge-pass' : 'badge-fail'}">${costStat}</span></td>
                <td><span class="${slaStat === 'PASS' ? 'badge-pass' : 'badge-fail'}">${slaStat}</span></td>
                <td><span class="${apStat === 'PASS' ? 'badge-pass' : 'badge-fail'}">${apStat}</span></td>
                <td><span class="${arStat === 'PASS' ? 'badge-pass' : 'badge-fail'}">${arStat}</span></td>
                <td><span class="${invStat === 'PASS' ? 'badge-pass' : 'badge-fail'}">${invStat}</span></td>
                <td><span class="${data.readiness_status === 'READY' ? 'badge-success' : 'badge-fail'}">${data.readiness_status}</span></td>
            `;
            elements.moduleMatrixTbody.appendChild(tr);
        });
    }

    // =========================================================================
    // BLOCKERS HUB
    // =========================================================================

    function updateBlockersHub(readiness) {
        state.blockers = [];
        const report = readiness.ledgers_report || {};

        Object.entries(report).forEach(([ledgerName, ldata]) => {
            if (ldata.detailed_blockers) {
                ldata.detailed_blockers.forEach((b) => {
                    state.blockers.push({
                        ...b,
                        ledgerName: ledgerName,
                        ledgerId: ldata.ledger_id,
                    });
                });
            }
        });

        filterBlockersTable();
    }

    function filterBlockersTable() {
        const searchTerm = elements.blockerSearchInput.value.toLowerCase();
        const selectedModule = elements.blockerModuleFilter.value;

        const filtered = state.blockers.filter((b) => {
            const matchModule =
                selectedModule === "ALL" || b.category === selectedModule;
            const fullText = `${b.transaction_id || ""} ${b.po_number || ""} ${b.receipt_number || ""} ${b.item_number || ""} ${b.supplier || ""} ${b.customer || ""} ${b.error_message || ""} ${b.ledgerName || ""}`.toLowerCase();
            const matchSearch = fullText.includes(searchTerm);
            return matchModule && matchSearch;
        });

        renderBlockersTable(filtered);
    }

    function renderBlockersTable(blockers) {
        elements.blockersTbody.innerHTML = "";

        if (blockers.length === 0) {
            elements.noBlockersMessage.style.display = "block";
            elements.blockersTable.style.display = "none";
            return;
        }

        elements.noBlockersMessage.style.display = "none";
        elements.blockersTable.style.display = "table";

        blockers.forEach((b, idx) => {
            const tr = document.createElement("tr");
            const ref = b.transaction_id || b.receipt_number || b.po_number || `REC-${idx + 1}`;
            const details = b.item_number
                ? `Item: ${b.item_number} (${b.quantity || ""})`
                : b.supplier
                ? `Supplier: ${b.supplier}`
                : b.customer
                ? `Customer: ${b.customer}`
                : b.organization
                ? `Org: ${b.organization}`
                : "General";

            tr.innerHTML = `
                <td><span class="badge-fail">CRITICAL</span></td>
                <td><strong>${b.module}</strong></td>
                <td><code>${ref}</code></td>
                <td>${b.ledgerName} (${b.ledgerId})</td>
                <td>${details}</td>
                <td style="max-width: 320px; font-size:12px; color:#c53030;">${escapeHtml(b.error_message || "Hold error")}</td>
                <td>
                    <button class="btn-secondary-sm btn-inspect-blocker" data-index="${idx}">
                        Inspect & Resolve
                    </button>
                </td>
            `;

            tr.querySelector(".btn-inspect-blocker").addEventListener("click", () => {
                showBlockerModal(b);
            });

            elements.blockersTbody.appendChild(tr);
        });
    }

    function showBlockerModal(blocker) {
        elements.modalTitle.textContent = `Blocker: ${blocker.transaction_id || blocker.receipt_number || blocker.module}`;
        elements.modalBodyContent.innerHTML = `
            <div class="detail-row">
                <span class="detail-label">Module:</span>
                <span class="detail-value">${blocker.module}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Target Ledger:</span>
                <span class="detail-value">${blocker.ledgerName} (${blocker.ledgerId})</span>
            </div>
            ${blocker.po_number && blocker.po_number !== "N/A" ? `
            <div class="detail-row">
                <span class="detail-label">Purchase Order:</span>
                <span class="detail-value">${blocker.po_number}</span>
            </div>` : ""}
            ${blocker.receipt_number && blocker.receipt_number !== "N/A" ? `
            <div class="detail-row">
                <span class="detail-label">Receipt Number:</span>
                <span class="detail-value">${blocker.receipt_number}</span>
            </div>` : ""}
            ${blocker.item_number && blocker.item_number !== "N/A" ? `
            <div class="detail-row">
                <span class="detail-label">Item / Product:</span>
                <span class="detail-value">${blocker.item_number} (${blocker.quantity || ""})</span>
            </div>` : ""}
            ${blocker.supplier && blocker.supplier !== "N/A" ? `
            <div class="detail-row">
                <span class="detail-label">Supplier:</span>
                <span class="detail-value">${blocker.supplier}</span>
            </div>` : ""}
            ${blocker.costing_status ? `
            <div class="detail-row">
                <span class="detail-label">Costing Status:</span>
                <span class="detail-value">${blocker.costing_status}</span>
            </div>` : ""}
            ${blocker.accounting_status ? `
            <div class="detail-row">
                <span class="detail-label">Accounting Status:</span>
                <span class="detail-value">${blocker.accounting_status}</span>
            </div>` : ""}
            ${blocker.transfer_status ? `
            <div class="detail-row">
                <span class="detail-label">Transfer to GL / CM:</span>
                <span class="detail-value">${blocker.transfer_status}</span>
            </div>` : ""}
            <div style="margin-top: 10px;">
                <strong>Oracle Error / Root Cause:</strong>
                <p style="color: #c53030; font-size: 13px; margin-top: 4px;">${escapeHtml(blocker.error_message || "")}</p>
            </div>
            <div class="resolution-step-box">
                <h4>👉 Recommended Resolution Playbook:</h4>
                <p>${escapeHtml(blocker.next_step || "Resolve transaction in Oracle Fusion.")}</p>
            </div>
        `;
        elements.resolutionModal.style.display = "flex";
    }

    function closeModal() {
        elements.resolutionModal.style.display = "none";
    }

    // =========================================================================
    // TESTING SUITE
    // =========================================================================

    async function run8CaseTestPack() {
        elements.testTerminalOutput.textContent = "Executing 8-Case Period Close Test Pack...\nConnecting to mock Oracle Fusion client...";
        try {
            const res = await fetch("/api/test-pack");
            const data = await res.json();
            if (data.status === "SUCCESS") {
                renderTestPackResults(data.cases, data.summary);
                elements.testTerminalOutput.textContent = data.logs;
            } else {
                elements.testTerminalOutput.textContent = `Test pack failed: ${data.error}`;
            }
        } catch (err) {
            elements.testTerminalOutput.textContent = `Execution error: ${err.message}`;
        }
    }

    function renderTestPackResults(cases, summary) {
        cases.forEach((c) => {
            const el = document.getElementById(`test-case-${c.case_num}-status`);
            if (el) {
                if (c.passed) {
                    el.innerHTML = `<span class="status-pill pass">PASS (${c.actual_status})</span>`;
                } else {
                    el.innerHTML = `<span class="status-pill fail">FAIL (${c.actual_status})</span>`;
                }
            }
        });

        if (summary) {
            elements.testPackStatsBanner.innerHTML = `
                <span class="badge-success">Passed: ${summary.passed}/${summary.total}</span>
                <span class="badge-neutral">Positive Rate: ${summary.positive_rate}% (Expected: 75%)</span>
            `;
        }
    }

    async function runUnitTests() {
        elements.testTerminalOutput.textContent = "Running Python unittest suite (test_period_close_8_case_pack.py & test_purchase_order_receipt.py)...\n";
        try {
            const res = await fetch("/api/unit-tests");
            const data = await res.json();
            elements.testTerminalOutput.textContent = data.output || "No output returned.";
        } catch (err) {
            elements.testTerminalOutput.textContent = `Unit test error: ${err.message}`;
        }
    }

    // =========================================================================
    // CONFIGURATION
    // =========================================================================

    async function saveConfiguration(e) {
        e.preventDefault();
        const mode = elements.cfgMode.value;
        const url = elements.cfgUrl.value.trim();
        const username = elements.cfgUsername.value.trim();
        const password = elements.cfgPassword.value;

        try {
            const res = await fetch("/api/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode, url, username, password }),
            });
            const data = await res.json();
            if (data.status === "SUCCESS") {
                showConfigAlert("Configuration saved successfully!", "success");
                state.mode = mode;
                updateConnectionIndicator(mode);
            } else {
                showConfigAlert(data.error || "Failed to save configuration.", "error");
            }
        } catch (err) {
            showConfigAlert(err.message, "error");
        }
    }

    async function testConnection() {
        const url = elements.cfgUrl.value.trim();
        const username = elements.cfgUsername.value.trim();
        const password = elements.cfgPassword.value;

        showConfigAlert("Testing connection to Oracle Fusion REST API...", "success");

        try {
            const res = await fetch("/api/test-connection", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url, username, password }),
            });
            const data = await res.json();
            if (data.status === "SUCCESS") {
                showConfigAlert(`Connection Successful! ${data.message}`, "success");
            } else {
                showConfigAlert(`Connection Failed: ${data.error}`, "error");
            }
        } catch (err) {
            showConfigAlert(`Network Error: ${err.message}`, "error");
        }
    }

    function showConfigAlert(msg, type) {
        elements.configStatusAlert.textContent = msg;
        elements.configStatusAlert.className = `alert-box ${type}`;
        elements.configStatusAlert.style.display = "block";
    }

    function updateConnectionIndicator(mode) {
        if (mode === "REAL") {
            elements.connectionPill.innerHTML = `
                <span class="status-dot live"></span>
                <span class="status-mode-label">LIVE ORACLE FUSION</span>
            `;
            elements.cfgMode.value = "REAL";
        } else {
            elements.connectionPill.innerHTML = `
                <span class="status-dot simulation"></span>
                <span class="status-mode-label">MOCK SIMULATION</span>
            `;
            elements.cfgMode.value = "MOCK";
        }
    }

    // =========================================================================
    // UTILITIES
    // =========================================================================

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function renderSimpleMarkdown(md) {
        if (!md) return "";
        let html = md;

        // Escape raw HTML except for our markdown transformations
        // Header 3
        html = html.replace(/^### (.*$)/gim, "<h3>$1</h3>");
        // Header 4
        html = html.replace(/^#### (.*$)/gim, "<h4>$1</h4>");
        // Bold
        html = html.replace(/\*\*(.*?)\*\*/gim, "<strong>$1</strong>");
        // Italic
        html = html.replace(/\*(.*?)\*/gim, "<em>$1</em>");
        // Inline code
        html = html.replace(/`(.*?)`/gim, "<code>$1</code>");
        // Bullet list
        html = html.replace(/^\- (.*$)/gim, "<li>$1</li>");
        html = html.replace(/^\* (.*$)/gim, "<li>$1</li>");
        // Numbered list
        html = html.replace(/^\d+\. (.*$)/gim, "<li>$1</li>");

        // Wrap list items
        html = html.replace(/(<li>.*<\/li>)/gims, "<ul>$1</ul>");

        // Paragraphs
        html = html
            .split("\n\n")
            .map((p) => {
                if (p.startsWith("<h") || p.startsWith("<ul") || p.startsWith("<li")) return p;
                return `<p>${p}</p>`;
            })
            .join("");

        return html;
    }

    // Start App
    init();
});
