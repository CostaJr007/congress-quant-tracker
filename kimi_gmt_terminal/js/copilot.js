/* CongressQuant CI://TERMINAL — AI Copilot Desk Agent */
window.GMT = window.GMT || {};
(function (G) {
  "use strict";

  const el = (tag, attrs = {}, children = []) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "style") node.style.cssText = v;
      else if (k === "text") node.textContent = v;
      else if (k === "html") node.innerHTML = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2).toLowerCase(), v);
      else node.setAttribute(k, v);
    }
    if (!Array.isArray(children)) children = [children];
    for (const c of children) {
      if (!c) continue;
      if (typeof c === "string" || typeof c === "number") node.appendChild(document.createTextNode(c));
      else node.appendChild(c);
    }
    return node;
  };

  const Copilot = {
    isOpen: false,
    provider: "groq",
    history: [],
    isBusy: false,

    init() {
      this.injectButton();
      this.createDrawer();
      this.loadModels();
      this.bindKeys();
    },

    injectButton() {
      const bar = document.getElementById("cmdbar");
      if (!bar) return;
      const btn = el("button", {
        id: "btn-ai-copilot",
        class: "seg btn-ai",
        style: "background:rgba(242,140,0,0.15);border:1px solid var(--org);color:var(--org);font-weight:800;cursor:pointer;padding:3px 10px;margin-left:auto;display:flex;align-items:center;gap:6px;",
        title: "Abrir Assistente Quantitativo de IA [F2]",
        onclick: () => this.toggle(),
      }, [
        el("span", { style: "font-size:11px;" }, "✦ AI://COPILOT"),
        el("span", { style: "font-size:9px;background:var(--org);color:#000;padding:1px 4px;border-radius:2px;font-weight:800;" }, "F2"),
      ]);
      bar.appendChild(btn);
    },

    createDrawer() {
      const drawer = el("aside", {
        id: "ai-drawer",
        class: "ai-drawer",
        style: "position:fixed;top:0;right:0;width:440px;height:100vh;background:#050505;border-left:1px solid #3A3A3A;box-shadow:-8px 0 24px rgba(0,0,0,0.8);z-index:9999;display:none;flex-direction:column;font-family:var(--mono);color:var(--ink);",
      });

      // 1. Header
      const head = el("div", {
        style: "display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#0A0A0A;border-bottom:1px solid #292929;",
      }, [
        el("div", { style: "display:flex;align-items:center;gap:8px;" }, [
          el("span", { style: "color:var(--org);font-weight:800;font-size:12px;" }, "CI://COPILOT"),
          el("span", { style: "font-size:9px;color:var(--up);background:rgba(0,193,118,0.15);border:1px solid var(--up);padding:1px 5px;border-radius:2px;" }, "ONLINE"),
        ]),
        el("div", { style: "display:flex;align-items:center;gap:8px;" }, [
          el("select", {
            id: "ai-provider-select",
            style: "background:#121212;border:1px solid #3A3A3A;color:var(--ink);font-size:10px;padding:2px 6px;cursor:pointer;",
            onchange: (e) => { this.provider = e.target.value; },
          }, [
            el("option", { value: "groq" }, "Groq (Llama 70B — Fast)"),
            el("option", { value: "openai" }, "OpenAI (GPT-4o Mini)"),
            el("option", { value: "local" }, "Local Llama (Kolmogorov)"),
          ]),
          el("button", {
            style: "color:var(--ink-dim);cursor:pointer;font-size:13px;padding:2px 6px;border:1px solid transparent;",
            title: "Limpar conversa",
            onclick: () => this.clearChat(),
          }, "↺"),
          el("button", {
            style: "color:var(--ink);cursor:pointer;font-size:14px;padding:2px 6px;",
            title: "Fechar [Esc]",
            onclick: () => this.toggle(false),
          }, "✕"),
        ]),
      ]);

      // 2. Categorized Quick Prompts Bar
      const pillsContainer = el("div", {
        id: "ai-pills-bar",
        style: "display:flex;flex-direction:column;gap:4px;padding:6px 10px;background:#080808;border-bottom:1px solid #1C1C1C;",
      });

      const categories = [
        {
          label: "🏛️ CONGRESS",
          pills: [
            ["Nancy Pelosi", "Mostre os trades oficiais da Nancy Pelosi com data, ativo, tipo de ordem e retornos."],
            ["John McGuire", "Faça o dossiê completo de compras e histórico de John McGuire."],
            ["Josh Gottheimer", "Quais as principais compras e vendas de Josh Gottheimer?"],
          ]
        },
        {
          label: "🏆 RANKINGS",
          pills: [
            ["Top 5 Retornos", "Quem são os top 5 deputados com maior retorno médio no ranking geral?"],
            ["Top PnL ($)", "Quais congressistas acumulam o maior lucro estimado em dólares?"],
            ["Compras Agosto/26", "Quem são os maiores compradores em Agosto de 2026? Gere uma tabela."],
          ]
        },
        {
          label: "🎯 ATIVOS & OPÇÕES",
          pills: [
            ["NVDA Sentimento", "Como os congressistas estão posicionados em NVDA? Calcule a taxa de compras vs vendas."],
            ["Opções (Calls/Puts)", "Quais congressistas negociaram opções de ações e em quais empresas?"],
            ["Setores em Alta", "Qual o setor mais acumulado pelos congressistas e qual o sentimento atual?"],
          ]
        },
        {
          label: "🚨 SUSPEITA",
          pills: [
            ["Trades Suspeitos", "Quais as 5 operações com maior score de suspeita no banco? Explique os motivos."],
            ["(R) vs (D)", "Compare o volume financeiro e o perfil de compras entre Republicanos e Democratas."],
            ["Últimas Notícias", "Resuma as principais notícias e eventos macroeconômicos do dia."],
          ]
        }
      ];

      const catBar = el("div", { style: "display:flex;gap:4px;overflow-x:auto;padding-bottom:3px;scrollbar-width:none;" });
      const chipsRow = el("div", { id: "ai-chips-row", style: "display:flex;gap:4px;overflow-x:auto;padding:2px 0;scrollbar-width:none;" });

      const renderCategoryChips = (idx) => {
        chipsRow.innerHTML = "";
        categories[idx].pills.forEach(([lab, query]) => {
          chipsRow.appendChild(this.createPill(lab, query));
        });
      };

      categories.forEach((cat, idx) => {
        const catBtn = el("button", {
          class: idx === 0 ? "on" : "",
          style: (idx === 0 ? "background:var(--org);color:#000;font-weight:800;" : "background:#121212;color:var(--ink-dim);") + "font-size:9px;padding:2px 6px;border:1px solid #2C2C2C;cursor:pointer;border-radius:2px;white-space:nowrap;",
          text: cat.label,
          onclick: (e) => {
            catBar.querySelectorAll("button").forEach(b => { b.style.background = "#121212"; b.style.color = "var(--ink-dim)"; b.style.fontWeight = "normal"; });
            catBtn.style.background = "var(--org)";
            catBtn.style.color = "#000";
            catBtn.style.fontWeight = "800";
            renderCategoryChips(idx);
          }
        });
        catBar.appendChild(catBtn);
      });

      renderCategoryChips(0);
      pillsContainer.appendChild(catBar);
      pillsContainer.appendChild(chipsRow);

      // 3. Messages Body
      const messagesContainer = el("div", {
        id: "ai-messages",
        style: "flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:12px;background:#050505;",
      });

      // Delegated click on interactive prompt cards
      messagesContainer.addEventListener("click", (e) => {
        const btn = e.target.closest(".clickable-prompt-btn, [data-query]");
        if (btn) {
          const q = btn.getAttribute("data-query");
          if (q) {
            this.sendPrompt(q);
          }
        }
      });

      // 4. Input Area
      const inputBar = el("div", {
        style: "padding:10px;background:#0A0A0A;border-top:1px solid #292929;display:flex;flex-direction:column;gap:6px;",
      }, [
        el("div", { style: "display:flex;gap:6px;" }, [
          el("textarea", {
            id: "ai-input-text",
            placeholder: "Pergunte sobre deputados, ações, retornos, opções ou relatórios...",
            rows: "2",
            style: "flex:1;background:#0E0E0E;border:1px solid #3A3A3A;color:var(--ink);padding:6px 8px;font-size:11px;resize:none;outline:none;font-family:var(--mono);",
            onkeydown: (e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                this.sendCurrent();
              }
            },
          }),
          el("button", {
            id: "ai-btn-send",
            style: "background:var(--org);color:#000;font-weight:800;padding:0 14px;border:none;cursor:pointer;font-size:11px;display:flex;align-items:center;justify-content:center;",
            onclick: () => this.sendCurrent(),
          }, "RUN ▶"),
        ]),
        el("div", { style: "display:flex;justify-content:space-between;font-size:9px;color:var(--ink-faint);" }, [
          el("span", {}, "Shift+Enter pula linha · Enter envia"),
          el("span", {}, "CI://AGENT LIVE ENGINE"),
        ]),
      ]);

      drawer.appendChild(head);
      drawer.appendChild(pillsContainer);
      drawer.appendChild(messagesContainer);
      drawer.appendChild(inputBar);
      document.body.appendChild(drawer);

      // Add Welcome Message with Interactive 1-Click Prompt Cards
      this.addMessage("assistant",
        "Olá! Sou o **CI://COPILOT**, seu analista quantitativo de inteligência parlamentar.\n\n" +
        "Tenho conexão direta com o banco SQLite oficial (**2.947 trades**, 95 parlamentares, retornos de mercado, opções e índices de suspeita).\n\n" +
        "💡 **Clique em qualquer pergunta abaixo para executar diretamente:**\n" +
        "- *\"Quais os últimos trades da Nancy Pelosi e o retorno de cada um?\"*\n" +
        "- *\"Quem são os top 5 deputados com maior retorno no ranking?\"*\n" +
        "- *\"Como os congressistas estão posicionados em NVDA?\"*\n" +
        "- *\"Quais congressistas operaram opções de compra (Calls) no ano?\"*\n" +
        "- *\"Quais foram as 5 operações com maior score de suspeita?\"*\n\n" +
        "Ou use as abas no topo para mais tópicos!"
      );
    },

    createPill(label, query) {
      return el("button", {
        style: "font-size:9px;padding:3px 8px;background:#141414;border:1px solid #333;color:var(--org);cursor:pointer;border-radius:2px;white-space:nowrap;font-weight:700;",
        onclick: () => {
          this.sendPrompt(query);
        },
      }, label);
    },

    sendPrompt(query) {
      const input = document.getElementById("ai-input-text");
      if (input) {
        input.value = query;
        this.sendCurrent();
      }
    },

    toggle(forceState) {
      const drawer = document.getElementById("ai-drawer");
      if (!drawer) return;
      this.isOpen = forceState !== undefined ? forceState : !this.isOpen;
      drawer.style.display = this.isOpen ? "flex" : "none";
      if (this.isOpen) {
        const input = document.getElementById("ai-input-text");
        if (input) input.focus();
      }
    },

    clearChat() {
      this.history = [];
      const cont = document.getElementById("ai-messages");
      if (cont) cont.innerHTML = "";
      this.addMessage("assistant", "Conversa reiniciada. Em que posso colaborar?");
    },

    async loadModels() {
      try {
        const res = await fetch("/api/terminal/chat/models");
        if (res.ok) {
          const data = await res.json();
          const sel = document.getElementById("ai-provider-select");
          if (sel && data.providers) {
            sel.innerHTML = "";
            data.providers.forEach(p => {
              const opt = document.createElement("option");
              opt.value = p.id;
              opt.textContent = `${p.name} [${p.badge}]`;
              if (p.is_default) opt.selected = true;
              sel.appendChild(opt);
            });
            this.provider = data.default_provider || "groq";
          }
        }
      } catch (e) {
        console.warn("Could not load AI models list:", e);
      }
    },

    bindKeys() {
      window.addEventListener("keydown", (e) => {
        if (e.key === "F2") {
          e.preventDefault();
          this.toggle();
        } else if (e.key === "Escape" && this.isOpen) {
          this.toggle(false);
        }
      });
    },

    formatMarkdown(text) {
      if (!text) return "";
      let html = text
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        // Interactive Clickable Prompt Cards from Bullet Lists with Quotes
        .replace(/^\s*[-•▪]\s*[*_]["“](.*?)["”][*_]\s*$/gim, (match, p1) => {
          const rawQ = p1.replace(/"/g, "&quot;");
          return `<div class="clickable-prompt-btn" data-query="${rawQ}" style="cursor:pointer;background:#101418;border:1px solid #2B3A4A;padding:5px 8px;margin:3px 0;border-radius:3px;display:flex;align-items:center;justify-content:space-between;color:var(--org);font-size:10px;font-weight:700;user-select:none;" onmouseover="this.style.borderColor='var(--org)';this.style.background='#1A1408'" onmouseout="this.style.borderColor='#2B3A4A';this.style.background='#101418'"><span><span style="color:#00C176;margin-right:6px">▶</span>&ldquo;${p1}&rdquo;</span><span style="font-size:8px;background:rgba(242,140,0,0.15);border:1px solid var(--org);color:var(--org);padding:1px 4px;border-radius:2px;flex-shrink:0">CLICK TO RUN</span></div>`;
        })
        // Bold
        .replace(/\*\*(.*?)\*\*/g, "<strong style='color:var(--org)'>$1</strong>")
        // Headers
        .replace(/^### (.*$)/gim, "<div style='font-size:12px;font-weight:800;color:var(--org);margin:8px 0 4px;'>$1</div>")
        .replace(/^## (.*$)/gim, "<div style='font-size:13px;font-weight:800;color:var(--org);margin:10px 0 4px;border-bottom:1px solid #292929;padding-bottom:2px;'>$1</div>")
        .replace(/^# (.*$)/gim, "<div style='font-size:14px;font-weight:800;color:var(--org);margin:12px 0 6px;'>$1</div>")
        // General Lists
        .replace(/^\s*[-•]\s*(.*$)/gim, "<div style='margin-left:8px;padding:1px 0;'>▪ $1</div>");

      // Tables (Markdown | col | col |)
      if (html.includes("|")) {
        const lines = html.split("\n");
        let inTable = false;
        let tableHtml = "<table style='width:100%;border-collapse:collapse;margin:8px 0;font-size:10px;border:1px solid #2A2A2A;'>";
        let newLines = [];

        for (let i = 0; i < lines.length; i++) {
          const l = lines[i].trim();
          if (l.startsWith("|") && l.endsWith("|")) {
            if (l.includes("---")) continue; // separator
            if (!inTable) {
              inTable = true;
              tableHtml = "<table style='width:100%;border-collapse:collapse;margin:8px 0;font-size:10px;border:1px solid #2A2A2A;'>";
            }
            const cells = l.split("|").slice(1, -1);
            const isHeader = !inTable || i === 0 || lines[i+1]?.includes("---");
            const tag = isHeader ? "th" : "td";
            const bg = isHeader ? "background:#141414;color:var(--org);font-weight:800;" : "background:#0A0A0A;border-bottom:1px solid #1C1C1C;";
            tableHtml += "<tr>" + cells.map(c => `<${tag} style='padding:4px 6px;border:1px solid #292929;text-align:left;${bg}'>${c.trim()}</${tag}>`).join("") + "</tr>";
          } else {
            if (inTable) {
              inTable = false;
              tableHtml += "</table>";
              newLines.push(tableHtml);
            }
            newLines.push(l);
          }
        }
        if (inTable) {
          tableHtml += "</table>";
          newLines.push(tableHtml);
        }
        html = newLines.join("<br/>");
      } else {
        html = html.replace(/\n/g, "<br/>");
      }
      return html;
    },

    addMessage(role, content) {
      const cont = document.getElementById("ai-messages");
      if (!cont) return null;

      const isUser = role === "user";
      const wrap = el("div", {
        style: `display:flex;flex-direction:column;gap:3px;align-self:${isUser ? "flex-end" : "flex-start"};max-width:92%;`,
      }, [
        el("div", {
          style: `font-size:9px;font-weight:800;color:${isUser ? "var(--cyan)" : "var(--org)"};letter-spacing:0.5px;`,
        }, isUser ? "YOU" : "CI://COPILOT"),
        el("div", {
          class: "msg-body",
          style: `background:${isUser ? "#141C1B" : "#0A0A0A"};border:1px solid ${isUser ? "#1C3633" : "#222222"};padding:8px 10px;border-radius:2px;font-size:11px;line-height:1.5;color:var(--ink);`,
          html: this.formatMarkdown(content),
        }),
      ]);

      cont.appendChild(wrap);
      cont.scrollTop = cont.scrollHeight;
      return wrap;
    },

    async sendCurrent() {
      if (this.isBusy) return;
      const input = document.getElementById("ai-input-text");
      if (!input) return;
      const text = input.value.trim();
      if (!text) return;

      input.value = "";
      this.isBusy = true;
      const sendBtn = document.getElementById("ai-btn-send");
      if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.textContent = "WAIT…";
      }

      this.addMessage("user", text);
      this.history.push({ role: "user", content: text });

      // Thinking indicator
      const thinking = this.addMessage("assistant", "⚡ *Consultando dados oficiais e calculando métricas...*");

      try {
        const resp = await fetch("/api/terminal/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: this.history,
            provider: this.provider,
          }),
        });

        if (!resp.ok) {
          const errText = await resp.text();
          throw new Error(`Status ${resp.status}: ${errText.slice(0, 100)}`);
        }

        const data = await resp.json();
        const content = data.content || "Nenhuma resposta gerada.";
        this.history.push({ role: "assistant", content });

        if (thinking) {
          const msgBody = thinking.querySelector(".msg-body");
          if (msgBody) msgBody.innerHTML = this.formatMarkdown(content);
        }
      } catch (err) {
        if (thinking) {
          const msgBody = thinking.querySelector(".msg-body");
          if (msgBody) msgBody.innerHTML = `<span style='color:var(--dn)'>⚠️ Erro ao consultar IA: ${err.message}</span>`;
        }
      } finally {
        this.isBusy = false;
        if (sendBtn) {
          sendBtn.disabled = false;
          sendBtn.textContent = "RUN ▶";
        }
        const cont = document.getElementById("ai-messages");
        if (cont) cont.scrollTop = cont.scrollHeight;
      }
    },
  };

  G.copilot = Copilot;
  document.addEventListener("DOMContentLoaded", () => Copilot.init());
})(window.GMT);
