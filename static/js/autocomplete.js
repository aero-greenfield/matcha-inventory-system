// Autocomplete / typeahead for material and recipe name inputs
// Usage: attachAutocomplete(inputElement, fetchFn)
//   fetchFn must return a Promise<string[]>

let _activeDropdown = null;

function _closeActiveDropdown() {
    if (_activeDropdown) {
        _activeDropdown.remove();
        _activeDropdown = null;
    }
}

function attachAutocomplete(input, fetchFn) {
    if (!input) return;

    let highlightedIndex = -1;
    let dropdown = null;

    function openDropdown(items) {
        _closeActiveDropdown();

        if (items.length === 0) return;

        dropdown = document.createElement('div');
        dropdown.className = 'autocomplete-dropdown';
        _activeDropdown = dropdown;

        items.slice(0, 10).forEach((raw, i) => {
            // Items may be plain strings (materials) or {name, badge} objects (recipes).
            const name = (typeof raw === 'string') ? raw : raw.name;
            const badge = (typeof raw === 'string') ? null : raw.badge;
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            // store the selectable value so keyboard/Enter selection ignores the badge text
            item.dataset.value = name;
            const nameSpan = document.createElement('span');
            nameSpan.textContent = name;
            item.appendChild(nameSpan);
            if (badge) {
                const badgeSpan = document.createElement('span');
                badgeSpan.className = 'badge badge-' + (badge === 'Component' ? 'mix' : 'finished');
                badgeSpan.textContent = badge;
                item.appendChild(badgeSpan);
            }
            item.addEventListener('mousedown', (e) => {
                e.preventDefault(); // prevent blur firing before click
                input.value = name;
                closeDropdown();
                input.dispatchEvent(new Event('change'));
            });
            item.addEventListener('mouseover', () => {
                highlightedIndex = i;
                updateHighlight();
            });
            dropdown.appendChild(item);
        });

        // Append inside the input's parent .form-group for absolute positioning
        const parent = input.closest('.form-group') || input.parentElement;
        parent.appendChild(dropdown);
        highlightedIndex = -1;
    }

    function closeDropdown() {
        if (dropdown) {
            dropdown.remove();
            dropdown = null;
            _activeDropdown = null;
        }
        highlightedIndex = -1;
    }

    function updateHighlight() {
        if (!dropdown) return;
        const items = dropdown.querySelectorAll('.autocomplete-item');
        items.forEach((item, i) => {
            item.classList.toggle('highlighted', i === highlightedIndex);
        });
    }

    // ADDED: debounce timer — fires the server request 250 ms after the user stops typing
    //        rather than on every keystroke, reducing request volume without feeling slow.
    let debounceTimer = null;

    input.addEventListener('input', () => {
        const query = input.value.trim();
        if (query.length === 0) {
            closeDropdown();
            return;
        }

        // ADDED: clear any pending request and schedule a new one after 250 ms
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            // CHANGED: fetchFn now receives the current query string and returns only
            //          matching results from the server (no client-side filtering needed).
            const matches = await fetchFn(query);
            openDropdown(matches);
        }, 250);
    });

    input.addEventListener('keydown', (e) => {
        if (!dropdown) return;
        const items = dropdown.querySelectorAll('.autocomplete-item');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            highlightedIndex = Math.min(highlightedIndex + 1, items.length - 1);
            updateHighlight();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            highlightedIndex = Math.max(highlightedIndex - 1, 0);
            updateHighlight();
        } else if (e.key === 'Enter') {
            if (highlightedIndex >= 0 && items[highlightedIndex]) {
                e.preventDefault();
                input.value = items[highlightedIndex].dataset.value;
                closeDropdown();
                input.dispatchEvent(new Event('change'));
            }
        } else if (e.key === 'Escape') {
            closeDropdown();
        }
    });

    input.addEventListener('blur', () => {
        // Delay so mousedown on item fires before blur closes the dropdown
        setTimeout(() => closeDropdown(), 150);
    });
}

// --- Server-side search fetchers ---
// REMOVED: _materialsCache / _recipesCache full-list caches — the server now filters by ?q=
//          so there is no full list to cache. Each call returns only matching names (≤50).
// ADDED: fetchMaterials(q) and fetchRecipes(q) — pass the current input to the server
//        and return the filtered results directly. No client-side filtering needed.

async function fetchMaterials(q = '') {
    const res = await fetch('/api/materials?q=' + encodeURIComponent(q), { credentials: 'include' });
    return res.json();
}

async function fetchRecipes(q = '') {
    const res = await fetch('/api/recipes?q=' + encodeURIComponent(q), { credentials: 'include' });
    const rows = await res.json();
    // /api/recipes returns [{name, batch_type}]; map to {name, badge} for the dropdown.
    return rows.map(function(r) {
        return { name: r.name, badge: r.batch_type === 'mix' ? 'Component' : 'Finished' };
    });
}
