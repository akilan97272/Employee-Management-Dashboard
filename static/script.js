// Simple JS for interactivity (e.g., listing block persons)
async function listBlock(block) {
    const response = await fetch(`/api/block_persons?block=${block}`);
    const data = await response.json();
    const listDiv = document.getElementById('block-list');
    listDiv.innerHTML = `<h3>Persons in ${block}</h3><ul>${data.persons.map(p => `<li>${p.name}</li>`).join('')}</ul>`;
}

// Add to main.py if needed: @app.get("/api/block_persons") to return persons in a block