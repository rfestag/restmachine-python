// Mermaid diagram fullscreen functionality
window.toggleMermaidFullscreen = function(button) {
    // Find the wrapper and then the next .mermaid element (can be div or pre)
    const wrapper = button.closest('.mermaid-fullscreen-wrapper');

    // Get the next element sibling (should be div.mermaid or pre.mermaid)
    let mermaidElement = wrapper.nextElementSibling;

    // Skip any text nodes
    while (mermaidElement && mermaidElement.nodeType === 3) {
        mermaidElement = mermaidElement.nextElementSibling;
    }

    // Verify it's a .mermaid element
    if (!mermaidElement || !mermaidElement.classList.contains('mermaid')) {
        console.error('No mermaid diagram found. Found instead:', mermaidElement);
        return;
    }

    // Debug: log what we found
    console.log('Found mermaid element:', mermaidElement);
    console.log('Element HTML:', mermaidElement.outerHTML.substring(0, 200));

    // Check if Mermaid has rendered an SVG - it might replace the entire pre element
    let svgElement = mermaidElement.querySelector('svg');

    if (!svgElement) {
        // Check if the pre.mermaid itself was replaced with a div or svg
        const nextSvg = mermaidElement.nextElementSibling;
        if (nextSvg && nextSvg.tagName === 'svg') {
            svgElement = nextSvg;
            mermaidElement = nextSvg;
        } else if (nextSvg && nextSvg.querySelector('svg')) {
            svgElement = nextSvg.querySelector('svg');
            mermaidElement = nextSvg;
        }
    }

    if (!svgElement) {
        console.error('Could not find rendered SVG. Element content:', mermaidElement.innerHTML.substring(0, 200));
        console.error('Next sibling:', mermaidElement.nextElementSibling);
        alert('Could not find the rendered diagram. Please check the browser console for details.');
        return;
    }

    console.log('Found SVG:', svgElement);

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
        closeBtn.onclick = () => {
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        };

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

        // Prevent buttons from triggering pan events
        [zoomInBtn, zoomOutBtn, resetBtn, closeBtn].forEach(btn => {
            btn.addEventListener('touchstart', (e) => e.stopPropagation());
            btn.addEventListener('touchmove', (e) => e.stopPropagation());
            btn.addEventListener('touchend', (e) => e.stopPropagation());
            btn.addEventListener('mousedown', (e) => e.stopPropagation());
        });

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
                document.body.style.overflow = '';
            }
        });

        // Close on background click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('active');
                document.body.style.overflow = '';
            }
        });

        // Zoom and pan functionality
        let scale = 15;  // Start zoomed in significantly
        let panX = 50;  // Start shifted right a bit
        let panY = 50;  // Start shifted down a bit
        let isPanning = false;
        let startX = 0;
        let startY = 0;
        const scaleStep = 0.3;  // Larger zoom steps
        const panStep = 50;  // Pixels to pan with arrow keys
        const minScale = 0.2;
        const maxScale = 15;  // Allow much more zoom

        function getPanLimits() {
            const container = content.querySelector('.diagram-wrapper');
            if (!container) return { minX: -Infinity, maxX: Infinity, minY: -Infinity, maxY: Infinity };

            const svg = container.querySelector('svg');
            if (!svg) return { minX: -Infinity, maxX: Infinity, minY: -Infinity, maxY: Infinity };

            const svgRect = svg.getBoundingClientRect();
            const contentRect = content.getBoundingClientRect();

            // Calculate limits to prevent panning beyond diagram
            const scaledWidth = svgRect.width;
            const scaledHeight = svgRect.height;

            return {
                minX: -(scaledWidth - contentRect.width + 200),
                maxX: 200,
                minY: -(scaledHeight - contentRect.height + 300), // Extra room for bottom
                maxY: 200
            };
        }

        function updateTransform() {
            const container = content.querySelector('.diagram-wrapper');
            if (container) {
                // Apply pan limits
                const limits = getPanLimits();
                panX = Math.max(limits.minX, Math.min(limits.maxX, panX));
                panY = Math.max(limits.minY, Math.min(limits.maxY, panY));

                container.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
            }
        }

        zoomInBtn.onclick = () => {
            scale = Math.min(maxScale, scale + scaleStep);
            updateTransform();
        };

        zoomOutBtn.onclick = () => {
            scale = Math.max(minScale, scale - scaleStep);
            updateTransform();
        };

        resetBtn.onclick = () => {
            scale = 15;
            panX = 50;
            panY = 50;
            updateTransform();
        };

        // Mouse wheel zoom (no Ctrl needed)
        content.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? -scaleStep : scaleStep;
            scale = Math.max(minScale, Math.min(maxScale, scale + delta));
            updateTransform();
        });

        // Arrow key panning
        document.addEventListener('keydown', (e) => {
            if (!overlay.classList.contains('active')) return;

            if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
                e.preventDefault();

                switch(e.key) {
                    case 'ArrowUp':
                        panY += panStep;
                        break;
                    case 'ArrowDown':
                        panY -= panStep;
                        break;
                    case 'ArrowLeft':
                        panX += panStep;
                        break;
                    case 'ArrowRight':
                        panX -= panStep;
                        break;
                }
                updateTransform();
            }
        });

        // Pan with mouse drag
        content.addEventListener('mousedown', (e) => {
            if (e.button === 0) {
                isPanning = true;
                startX = e.clientX - panX;
                startY = e.clientY - panY;
                content.style.cursor = 'grabbing';
            }
        });

        document.addEventListener('mousemove', (e) => {
            if (isPanning) {
                e.preventDefault();
                panX = e.clientX - startX;
                panY = e.clientY - startY;
                updateTransform();
            }
        });

        document.addEventListener('mouseup', () => {
            if (isPanning) {
                isPanning = false;
                content.style.cursor = '';
            }
        });

        // Touch support for mobile
        let lastTouchDistance = null;
        let touchStartPanX = 0;
        let touchStartPanY = 0;
        let isPinching = false;

        function getTouchDistance(touch1, touch2) {
            const dx = touch1.clientX - touch2.clientX;
            const dy = touch1.clientY - touch2.clientY;
            return Math.sqrt(dx * dx + dy * dy);
        }

        content.addEventListener('touchstart', (e) => {
            if (e.touches.length === 1) {
                // Single finger - prepare for panning (but don't start yet)
                isPanning = false;
                isPinching = false;
                startX = e.touches[0].clientX - panX;
                startY = e.touches[0].clientY - panY;
                touchStartPanX = panX;
                touchStartPanY = panY;
            } else if (e.touches.length === 2) {
                // Two fingers - start pinch zoom immediately
                e.preventDefault();
                isPanning = false;
                isPinching = true;
                lastTouchDistance = getTouchDistance(e.touches[0], e.touches[1]);
            }
        });

        content.addEventListener('touchmove', (e) => {
            if (e.touches.length === 1 && !isPinching) {
                // Single finger - pan (only if not pinching)
                e.preventDefault();
                isPanning = true;
                panX = e.touches[0].clientX - startX;
                panY = e.touches[0].clientY - startY;
                updateTransform();
            } else if (e.touches.length === 2) {
                // Two fingers - pinch zoom
                e.preventDefault();
                isPinching = true;
                isPanning = false;

                const newDistance = getTouchDistance(e.touches[0], e.touches[1]);
                if (lastTouchDistance) {
                    const scaleDelta = (newDistance - lastTouchDistance) * 0.015;
                    scale = Math.max(minScale, Math.min(maxScale, scale + scaleDelta));
                    updateTransform();
                }
                lastTouchDistance = newDistance;
            }
        });

        content.addEventListener('touchend', (e) => {
            if (e.touches.length === 0) {
                // All fingers lifted
                isPanning = false;
                isPinching = false;
                lastTouchDistance = null;
            } else if (e.touches.length === 1 && isPinching) {
                // One finger left after pinching - reset for panning
                isPinching = false;
                isPanning = false;
                lastTouchDistance = null;
                startX = e.touches[0].clientX - panX;
                startY = e.touches[0].clientY - panY;
            }
        });
    }

    // Clone and insert the diagram
    const content = overlay.querySelector('.mermaid-fullscreen-content');
    content.innerHTML = '';

    const clone = mermaidElement.cloneNode(true);
    const diagramWrapper = document.createElement('div');
    diagramWrapper.className = 'diagram-wrapper';
    diagramWrapper.style.transformOrigin = 'top left';

    // Apply initial zoom and pan immediately
    const initialScale = 15;
    const initialPanX = 50;
    const initialPanY = 50;
    diagramWrapper.style.transform = `translate(${initialPanX}px, ${initialPanY}px) scale(${initialScale})`;

    diagramWrapper.appendChild(clone);
    content.appendChild(diagramWrapper);

    // Update overlay's scale tracking to match initial values
    const updateFunc = overlay.updateTransform;
    if (updateFunc) {
        overlay.currentScale = initialScale;
        overlay.currentPanX = initialPanX;
        overlay.currentPanY = initialPanY;
    }

    // Prevent body scroll when overlay is open
    document.body.style.overflow = 'hidden';

    // Show overlay
    overlay.classList.add('active');
}

// Initialize Mermaid and attach fullscreen handlers
document.addEventListener('DOMContentLoaded', function() {
    console.log('Mermaid fullscreen support loaded');

    // Add loading spinners to all Mermaid diagrams
    document.querySelectorAll('.mermaid').forEach(function(mermaidElement) {
        // Create loading spinner
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'mermaid-loading';
        loadingDiv.innerHTML = '<div class="mermaid-spinner"></div><span class="mermaid-loading-text">Loading diagram...</span>';

        // Insert before the mermaid element
        mermaidElement.parentNode.insertBefore(loadingDiv, mermaidElement);
    });

    // Initialize Mermaid if available
    if (typeof mermaid !== 'undefined') {
        // Detect if we're in dark mode
        const isDarkMode = document.body.getAttribute('data-md-color-scheme') === 'slate';

        mermaid.initialize({
            startOnLoad: true,
            theme: 'default',  // Use default theme to respect inline styles
            themeVariables: {
                // Lines and arrows
                lineColor: '#5c6bc0',

                // Text colors
                textColor: '#333333',
                labelTextColor: '#333333',

                // Link/edge colors
                defaultLinkColor: '#5c6bc0'
            },
            flowchart: {
                useMaxWidth: true,
                htmlLabels: true,
                curve: 'basis'
            }
        });

        // Wait for Mermaid to render, then show diagrams and hide spinners
        setTimeout(function() {
            // Show all rendered Mermaid diagrams
            document.querySelectorAll('.mermaid').forEach(function(mermaidElement) {
                if (mermaidElement.querySelector('svg')) {
                    mermaidElement.classList.add('mermaid-ready');

                    // Remove the loading spinner
                    const loadingDiv = mermaidElement.previousElementSibling;
                    if (loadingDiv && loadingDiv.classList.contains('mermaid-loading')) {
                        loadingDiv.remove();
                    }
                }
            });

            // Attach click handlers to fullscreen buttons
            document.querySelectorAll('.mermaid-fullscreen-btn').forEach(function(button) {
                button.addEventListener('click', function() {
                    window.toggleMermaidFullscreen(this);
                });
            });
            console.log('Mermaid diagrams rendered and fullscreen buttons attached');
        }, 500);
    } else {
        console.warn('Mermaid library not loaded');

        // Remove spinners if Mermaid isn't available
        document.querySelectorAll('.mermaid-loading').forEach(function(spinner) {
            spinner.remove();
        });

        // Still attach handlers in case diagrams are rendered by other means
        document.querySelectorAll('.mermaid-fullscreen-btn').forEach(function(button) {
            button.addEventListener('click', function() {
                window.toggleMermaidFullscreen(this);
            });
        });
    }
});
