// Simple JS for interactivity (e.g., listing block persons)
async function listBlock(block) {
    const response = await fetch(`/api/block_persons?block=${block}`);
    const data = await response.json();
    const listDiv = document.getElementById('block-list');
    listDiv.innerHTML = `<h3>Persons in ${block}</h3><ul>${data.persons.map(p => `<li>${p.name}</li>`).join('')}</ul>`;
}

// Add to main.py if needed: @app.get("/api/block_persons") to return persons in a block

// Reload confirmation + logout flow
function isReloadNavigation() {
    const navEntries = performance.getEntriesByType && performance.getEntriesByType('navigation');
    if (navEntries && navEntries.length) {
        return navEntries[0].type === 'reload';
    }
    // Fallback for older browsers
    return performance.navigation && performance.navigation.type === 1;
}

function createReloadModal() {
    const overlay = document.createElement('div');
    overlay.id = 'reload-confirm-overlay';
    overlay.style.position = 'fixed';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.width = '100%';
    overlay.style.height = '100%';
    overlay.style.background = 'rgba(0, 0, 0, 0.45)';
    overlay.style.display = 'flex';
    overlay.style.alignItems = 'center';
    overlay.style.justifyContent = 'center';
    overlay.style.zIndex = '9999';

    const modal = document.createElement('div');
    modal.style.background = '#ffffff';
    modal.style.borderRadius = '12px';
    modal.style.maxWidth = '520px';
    modal.style.width = '92%';
    modal.style.boxShadow = '0 12px 36px rgba(0,0,0,0.2)';
    modal.style.padding = '20px 22px';
    modal.style.fontFamily = 'inherit';

    const title = document.createElement('div');
    title.textContent = 'Session Security Notice';
    title.style.fontSize = '18px';
    title.style.fontWeight = '600';
    title.style.marginBottom = '8px';

    const message = document.createElement('div');
    message.textContent = 'For your security, reloading will end your current session. Do you want to continue and log out?';
    message.style.fontSize = '14px';
    message.style.color = '#333';
    message.style.lineHeight = '1.5';
    message.style.marginBottom = '16px';

    const actions = document.createElement('div');
    actions.style.display = 'flex';
    actions.style.justifyContent = 'flex-end';
    actions.style.gap = '10px';

    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.style.padding = '8px 14px';
    cancelBtn.style.borderRadius = '8px';
    cancelBtn.style.border = '1px solid #cfd4dc';
    cancelBtn.style.background = '#ffffff';
    cancelBtn.style.cursor = 'pointer';

    const continueBtn = document.createElement('button');
    continueBtn.type = 'button';
    continueBtn.textContent = 'Continue';
    continueBtn.style.padding = '8px 14px';
    continueBtn.style.borderRadius = '8px';
    continueBtn.style.border = '1px solid #1f6feb';
    continueBtn.style.background = '#1f6feb';
    continueBtn.style.color = '#ffffff';
    continueBtn.style.cursor = 'pointer';

    cancelBtn.addEventListener('click', () => {
        overlay.remove();
    });

    continueBtn.addEventListener('click', () => {
        window.location.href = '/logout';
    });

    actions.appendChild(cancelBtn);
    actions.appendChild(continueBtn);

    modal.appendChild(title);
    modal.appendChild(message);
    modal.appendChild(actions);
    overlay.appendChild(modal);
    return overlay;
}

document.addEventListener('DOMContentLoaded', () => {
    if (isReloadNavigation()) {
        const modal = createReloadModal();
        document.body.appendChild(modal);
    }
});