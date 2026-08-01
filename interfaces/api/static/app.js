"use strict";

/** @typedef {Record<string, unknown>} JsonObject */

const STORAGE_KEY = "jdr_client_character_id";

const ABILITY_LABELS = {
  str: "FOR",
  dex: "DEX",
  con: "CON",
  int: "INT",
  wis: "SAG",
  cha: "CHA",
};

const el = {
  characterId: document.getElementById("character-id"),
  btnLoad: document.getElementById("btn-load"),
  spellId: document.getElementById("spell-id"),
  diceToSpend: document.getElementById("dice-to-spend"),
  btnCast: document.getElementById("btn-cast"),
  btnShortRest: document.getElementById("btn-short-rest"),
  btnLongRest: document.getElementById("btn-long-rest"),
  actionsHint: document.getElementById("actions-hint"),
  statusBanner: document.getElementById("status-banner"),
  actionResult: document.getElementById("action-result"),
  sheetEmpty: document.getElementById("sheet-empty"),
  sheetContent: document.getElementById("sheet-content"),
};

let activeCharacterId = "";

function formatModifier(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return value >= 0 ? `+${value}` : String(value);
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Extrait un message lisible depuis une réponse d'erreur FastAPI.
 * @param {Response} response
 * @param {unknown} body
 */
function extractErrorMessage(response, body) {
  if (body && typeof body === "object" && body !== null) {
    const detail = /** @type {{ detail?: unknown }} */ (body).detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            const loc = Array.isArray(item.loc) ? item.loc.join(".") : "";
            return loc ? `${loc} : ${item.msg}` : String(item.msg);
          }
          return JSON.stringify(item);
        })
        .join(" · ");
    }
  }
  if (typeof body === "string" && body.trim()) {
    return body.trim();
  }
  return response.statusText || "Erreur inconnue";
}

function showBanner(kind, message) {
  el.statusBanner.textContent = message;
  el.statusBanner.className = `visible ${kind}`;
}

function clearBanner() {
  el.statusBanner.className = "";
  el.statusBanner.textContent = "";
}

function setActionsEnabled(enabled) {
  el.btnCast.disabled = !enabled;
  el.btnShortRest.disabled = !enabled;
  el.btnLongRest.disabled = !enabled;
  el.actionsHint.classList.toggle("hidden", enabled);
}

function setBusy(busy) {
  el.btnLoad.disabled = busy;
  el.btnCast.disabled = busy || !activeCharacterId;
  el.btnShortRest.disabled = busy || !activeCharacterId;
  el.btnLongRest.disabled = busy || !activeCharacterId;
}

/**
 * @param {string} path
 * @param {RequestInit} [options]
 */
async function apiFetch(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
  } catch (err) {
    throw new Error(
      `Impossible de joindre le serveur (${path}). Vérifiez qu'uvicorn est lancé. Détail : ${err instanceof Error ? err.message : String(err)}`
    );
  }

  const contentType = response.headers.get("content-type") || "";
  let body = null;
  if (contentType.includes("application/json")) {
    try {
      body = await response.json();
    } catch {
      throw new Error(
        `Réponse JSON invalide (${response.status}) pour ${path}.`
      );
    }
  } else {
    const text = await response.text();
    if (text) {
      body = text;
    }
  }

  if (!response.ok) {
    const message = extractErrorMessage(response, body);
    throw new Error(`HTTP ${response.status} — ${message}`);
  }

  if (body === null || typeof body !== "object") {
    throw new Error(
      `Réponse inattendue pour ${path} : corps absent ou non JSON.`
    );
  }

  return /** @type {JsonObject} */ (body);
}

function renderTagList(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return "<p style='color:#71717a;margin:0;'>—</p>";
  }
  return `<ul class="tag-list">${items
    .map((item) => `<li>${escapeHtml(String(item))}</li>`)
    .join("")}</ul>`;
}

function renderSlots(slotsMax, slotsRemaining) {
  const max = slotsMax && typeof slotsMax === "object" ? slotsMax : {};
  const rem =
    slotsRemaining && typeof slotsRemaining === "object"
      ? slotsRemaining
      : {};
  const levels = Object.keys(max).sort((a, b) => Number(a) - Number(b));
  if (levels.length === 0) {
    return "<p style='color:#71717a;margin:0;'>Aucun emplacement</p>";
  }
  return `<ul class="tag-list">${levels
    .map((lvl) => {
      const r = rem[lvl] ?? 0;
      const m = max[lvl] ?? 0;
      return `<li>niv. ${escapeHtml(lvl)} : ${escapeHtml(String(r))}/${escapeHtml(String(m))}</li>`;
    })
    .join("")}</ul>`;
}

function renderSpellcasting(sc) {
  if (!sc || typeof sc !== "object") {
    return "";
  }
  const concentration =
    sc.concentration && typeof sc.concentration === "object"
      ? sc.concentration
      : null;
  const concText = concentration
    ? escapeHtml(
        String(concentration.spell_name || concentration.spell_id || "—")
      )
    : "—";

  return `
    <div class="stat-block">
      <dl>
        <dt>Magie de pacte</dt><dd>${sc.pact_magic ? "Oui" : "Non"}</dd>
        <dt>Caractéristique</dt><dd>${escapeHtml(String(sc.ability || "—"))}</dd>
        <dt>Concentration</dt><dd>${concText}</dd>
      </dl>
      <p style="margin:0.5rem 0 0.25rem;font-size:0.8125rem;color:#71717a;">Emplacements</p>
      ${renderSlots(sc.slots_max, sc.slots_remaining)}
      <p style="margin:0.75rem 0 0.25rem;font-size:0.8125rem;color:#71717a;">Tours de magie</p>
      ${renderTagList(sc.cantrips_known)}
      <p style="margin:0.75rem 0 0.25rem;font-size:0.8125rem;color:#71717a;">Préparés</p>
      ${renderTagList(sc.spells_prepared)}
      <p style="margin:0.75rem 0 0.25rem;font-size:0.8125rem;color:#71717a;">Connus</p>
      ${renderTagList(sc.spells_known)}
      <p style="margin:0.75rem 0 0.25rem;font-size:0.8125rem;color:#71717a;">Grimoire</p>
      ${renderTagList(sc.spellbook)}
      <p style="margin:0.75rem 0 0.25rem;font-size:0.8125rem;color:#71717a;">Domaine</p>
      ${renderTagList(sc.domain_spells)}
    </div>`;
}

function renderSavingThrows(entries) {
  if (!Array.isArray(entries) || entries.length === 0) {
    return "<p style='color:#71717a;margin:0;'>—</p>";
  }
  return `<ul class="tag-list">${entries
    .map((entry) => {
      const ability = ABILITY_LABELS[entry.ability_id] || entry.ability_id;
      const mod = formatModifier(entry.modifier);
      const mark = entry.proficient ? " ●" : "";
      const cls = entry.proficient ? "proficient" : "";
      return `<li class="${cls}">${escapeHtml(ability)} ${escapeHtml(mod)}${mark}</li>`;
    })
    .join("")}</ul>`;
}

function renderAbilities(scores, modifiers) {
  const ids = ["str", "dex", "con", "int", "wis", "cha"];
  const rows = ids
    .map((id) => {
      const score = scores && scores[id] != null ? scores[id] : "—";
      const mod =
        modifiers && modifiers[id] != null
          ? formatModifier(modifiers[id])
          : "—";
      return `<dt>${escapeHtml(ABILITY_LABELS[id])}</dt><dd>${escapeHtml(String(score))} (${escapeHtml(mod)})</dd>`;
    })
    .join("");
  return `<dl>${rows}</dl>`;
}

/** @param {JsonObject} sheet */
function renderSheet(sheet) {
  const classLine = sheet.specialization_label
    ? `${sheet.class_name} (${sheet.specialization_label})`
    : String(sheet.class_name || sheet.class_id || "—");

  const fightingStyle = sheet.fighting_style_label
    ? `<dt>Style de combat</dt><dd>${escapeHtml(String(sheet.fighting_style_label))}</dd>`
    : "";

  el.sheetContent.innerHTML = `
    <div class="sheet-header">
      <p class="name">${escapeHtml(String(sheet.name || "—"))}</p>
      <p class="meta">
        ${escapeHtml(String(sheet.race_name || sheet.race_id || "—"))} ·
        ${escapeHtml(classLine)} · niv. ${escapeHtml(String(sheet.level ?? "—"))}
        · id ${escapeHtml(String(sheet.character_id || "—"))}
      </p>
    </div>
    <div class="grid-2">
      <div class="stat-block">
        <h3 style="margin:0 0 0.5rem;font-size:0.875rem;">Combat</h3>
        <dl>
          <dt>PV</dt><dd>${escapeHtml(String(sheet.hp_current ?? "—"))} / ${escapeHtml(String(sheet.hp_max ?? "—"))}</dd>
          <dt>CA</dt><dd>${escapeHtml(String(sheet.ac ?? "—"))}</dd>
          <dt>Initiative</dt><dd>${escapeHtml(formatModifier(sheet.initiative))}</dd>
          <dt>Vitesse</dt><dd>${escapeHtml(String(sheet.speed ?? "—"))} pi</dd>
          <dt>Dés de vie</dt><dd>${escapeHtml(String(sheet.hit_dice_remaining ?? "—"))}/${escapeHtml(String(sheet.hit_dice_total ?? "—"))} ${escapeHtml(String(sheet.hit_die || ""))}</dd>
          <dt>Bonus de maîtrise</dt><dd>${escapeHtml(formatModifier(sheet.proficiency_bonus))}</dd>
          ${fightingStyle}
        </dl>
      </div>
      <div class="stat-block">
        <h3 style="margin:0 0 0.5rem;font-size:0.875rem;">Caractéristiques</h3>
        ${renderAbilities(sheet.ability_scores, sheet.ability_modifiers)}
      </div>
      <div class="stat-block">
        <h3 style="margin:0 0 0.5rem;font-size:0.875rem;">Jets de sauvegarde</h3>
        ${renderSavingThrows(sheet.saving_throws)}
      </div>
      <div class="stat-block">
        <h3 style="margin:0 0 0.5rem;font-size:0.875rem;">Compétences maîtrisées</h3>
        ${renderTagList(sheet.proficient_skill_ids)}
      </div>
      <div class="stat-block">
        <h3 style="margin:0 0 0.5rem;font-size:0.875rem;">Maîtrises d'armures</h3>
        ${renderTagList(sheet.armor_proficiencies)}
      </div>
      <div class="stat-block">
        <h3 style="margin:0 0 0.5rem;font-size:0.875rem;">Maîtrises d'armes</h3>
        ${renderTagList(sheet.weapon_proficiencies)}
      </div>
      <div class="stat-block">
        <h3 style="margin:0 0 0.5rem;font-size:0.875rem;">Résistances aux dégâts</h3>
        ${renderTagList(sheet.damage_resistances)}
      </div>
      <div class="stat-block">
        <h3 style="margin:0 0 0.5rem;font-size:0.875rem;">Traits raciaux</h3>
        ${renderTagList(sheet.trait_names)}
      </div>
      <div class="stat-block">
        <h3 style="margin:0 0 0.5rem;font-size:0.875rem;">Aptitudes de classe</h3>
        ${
          Array.isArray(sheet.class_features) && sheet.class_features.length
            ? `<ul class="tag-list">${sheet.class_features
                .map(
                  (f) =>
                    `<li title="${escapeHtml(String(f.feature_id || ""))}">${escapeHtml(String(f.name || f.feature_id || "—"))}</li>`
                )
                .join("")}</ul>`
            : "<p style='color:#71717a;margin:0;'>—</p>"
        }
      </div>
      ${
        sheet.spellcasting
          ? `<div class="stat-block"><h3 style="margin:0 0 0.5rem;font-size:0.875rem;">Incantation</h3>${renderSpellcasting(sheet.spellcasting)}</div>`
          : ""
      }
    </div>`;

  el.sheetEmpty.classList.add("hidden");
  el.sheetContent.classList.remove("hidden");
}

function showActionResult(data) {
  el.actionResult.classList.remove("empty");
  el.actionResult.textContent = JSON.stringify(data, null, 2);
}

async function loadSheet(characterId, options = {}) {
  const { silent = false } = options;
  const id = characterId.trim();
  if (!id) {
    throw new Error("Saisissez un identifiant de personnage.");
  }

  const sheet = await apiFetch(`/characters/${encodeURIComponent(id)}/sheet`);
  activeCharacterId = id;
  localStorage.setItem(STORAGE_KEY, id);
  renderSheet(sheet);
  setActionsEnabled(true);
  if (!silent) {
    showBanner("success", `Fiche chargée : ${sheet.name} (${id}).`);
  }
  return sheet;
}

async function handleLoad() {
  clearBanner();
  setBusy(true);
  try {
    await loadSheet(el.characterId.value);
  } catch (err) {
    activeCharacterId = "";
    setActionsEnabled(false);
    el.sheetEmpty.classList.remove("hidden");
    el.sheetContent.classList.add("hidden");
    showBanner(
      "error",
      err instanceof Error ? err.message : "Échec du chargement de la fiche."
    );
  } finally {
    setBusy(false);
  }
}

async function runAction(label, fn) {
  if (!activeCharacterId) {
    showBanner("error", "Chargez d'abord un personnage.");
    return;
  }
  clearBanner();
  setBusy(true);
  try {
    const result = await fn();
    showActionResult(result);
    showBanner("success", `${label} — succès. Fiche rechargée.`);
    await loadSheet(activeCharacterId, { silent: true });
  } catch (err) {
    showActionResult({});
    el.actionResult.classList.add("empty");
    el.actionResult.textContent = "Action en échec — voir le message ci-dessus.";
    showBanner(
      "error",
      err instanceof Error ? err.message : `${label} — échec inattendu.`
    );
  } finally {
    setBusy(false);
  }
}

el.btnLoad.addEventListener("click", () => {
  void handleLoad();
});

el.characterId.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    void handleLoad();
  }
});

el.btnCast.addEventListener("click", () => {
  const spellId = el.spellId.value.trim();
  if (!spellId) {
    showBanner("error", "Saisissez un spell_id.");
    return;
  }
  void runAction(`Lancer ${spellId}`, () =>
    apiFetch(`/characters/${encodeURIComponent(activeCharacterId)}/cast`, {
      method: "POST",
      body: JSON.stringify({ spell_id: spellId }),
    })
  );
});

el.btnShortRest.addEventListener("click", () => {
  const raw = el.diceToSpend.value;
  const dice = Number(raw);
  if (!Number.isInteger(dice) || dice < 0) {
    showBanner("error", "Le nombre de dés doit être un entier ≥ 0.");
    return;
  }
  void runAction(`Repos court (${dice} dé${dice > 1 ? "s" : ""})`, () =>
    apiFetch(
      `/characters/${encodeURIComponent(activeCharacterId)}/short-rest`,
      {
        method: "POST",
        body: JSON.stringify({ dice_to_spend: dice }),
      }
    )
  );
});

el.btnLongRest.addEventListener("click", () => {
  void runAction("Repos long", () =>
    apiFetch(`/characters/${encodeURIComponent(activeCharacterId)}/long-rest`, {
      method: "POST",
    })
  );
});

const savedId = localStorage.getItem(STORAGE_KEY);
if (savedId) {
  el.characterId.value = savedId;
}

setActionsEnabled(false);
