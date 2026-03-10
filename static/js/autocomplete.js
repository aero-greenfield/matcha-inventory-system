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

        items.slice(0, 10).forEach((name, i) => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.textContent = name;
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

    input.addEventListener('input', async () => {
        const query = input.value.trim().toLowerCase();
        if (query.length === 0) {
            closeDropdown();
            return;
        }
        const allNames = await fetchFn();
        const matches = allNames.filter(n => n.toLowerCase().includes(query));
        openDropdown(matches);
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
                input.value = items[highlightedIndex].textContent;
                closeDropdown();
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

// --- Cached fetchers ---

let _materialsCache = null;
async function fetchMaterials() {
    if (_materialsCache) return _materialsCache;
    const res = await fetch('/api/materials', { credentials: 'include' });
    _materialsCache = await res.json();
    return _materialsCache;
}

let _recipesCache = null;
async function fetchRecipes() {
    if (_recipesCache) return _recipesCache;
    const res = await fetch('/api/recipes', { credentials: 'include' });
    _recipesCache = await res.json();
    return _recipesCache;
}
