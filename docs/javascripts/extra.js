// Mermaid diagram fullscreen functionality
function toggleMermaidFullscreen(button) {
    // Find the next mermaid diagram after the button
    const wrapper = button.closest('.mermaid-fullscreen-wrapper');
    const mermaidDiv = wrapper.nextElementSibling;

    if (!mermaidDiv || !mermaidDiv.classList.contains('mermaid')) {
        console.error('No mermaid diagram found after button');
        return;
    }

    // Create overlay if it doesn't exist
    let overlay = document.querySelector('.mermaid-fullscreen-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'mermaid-fullscreen-overlay';

        const content = document.createElement('div');
        content.className = 'mermaid-fullscreen-content';

        const closeBtn = document.createElement('button');
        closeBtn.className = 'mermaid-fullscreen-close';
        closeBtn.innerHTML = '×';
        closeBtn.onclick = () => overlay.classList.remove('active');

        const controls = document.createElement('div');
        controls.className = 'mermaid-fullscreen-controls';

        const zoomInBtn = document.createElement('button');
        zoomInBtn.className = 'mermaid-zoom-btn';
        zoomInBtn.innerHTML = '+';
        zoomInBtn.title = 'Zoom In';

        const zoomOutBtn = document.createElement('button');
        zoomOutBtn.className = 'mermaid-zoom-btn';
        zoomOutBtn.innerHTML = '−';
        zoomOutBtn.title = 'Zoom Out';

        const resetBtn = document.createElement('button');
        resetBtn.className = 'mermaid-zoom-btn';
        resetBtn.innerHTML = '⊙';
        resetBtn.title = 'Reset Zoom';

        controls.appendChild(zoomInBtn);
        controls.appendChild(zoomOutBtn);
        controls.appendChild(resetBtn);

        overlay.appendChild(closeBtn);
        overlay.appendChild(controls);
        overlay.appendChild(content);
        document.body.appendChild(overlay);

        // Close on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && overlay.classList.contains('active')) {
                overlay.classList.remove('active');
            }
        });

        // Close on background click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('active');
            }
        });

        // Zoom functionality
        let scale = 1;
        const scaleStep = 0.2;
        const minScale = 0.5;
        const maxScale = 3;

        function updateScale(newScale) {
            scale = Math.max(minScale, Math.min(maxScale, newScale));
            const svg = content.querySelector('svg');
            if (svg) {
                svg.style.transform = `scale(${scale})`;
                svg.style.transformOrigin = 'top left';
            }
        }

        zoomInBtn.onclick = () => updateScale(scale + scaleStep);
        zoomOutBtn.onclick = () => updateScale(scale - scaleStep);
        resetBtn.onclick = () => updateScale(1);

        // Mouse wheel zoom
        content.addEventListener('wheel', (e) => {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                const delta = e.deltaY > 0 ? -scaleStep : scaleStep;
                updateScale(scale + delta);
            }
        });
    }

    // Clone and insert the diagram
    const content = overlay.querySelector('.mermaid-fullscreen-content');
    content.innerHTML = '';
    const clone = mermaidDiv.cloneNode(true);
    content.appendChild(clone);

    // Reset scale
    const svg = clone.querySelector('svg');
    if (svg) {
        svg.style.transform = 'scale(1)';
        svg.style.transformOrigin = 'top left';
    }

    // Show overlay
    overlay.classList.add('active');
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Mermaid fullscreen support loaded');
});
