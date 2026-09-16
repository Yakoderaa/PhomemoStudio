(() => {
  'use strict';

  const post = (type) => {
    try {
      if (window.chrome?.webview?.postMessage) {
        window.chrome.webview.postMessage({ type });
        return true;
      }
    } catch (e) {
      console.error('desktop message failed', e);
    }
    return false;
  };

  const wireDesktopControls = () => {
    const updateButton = document.getElementById('applePlaceholderBtn');
    if (updateButton) {
      updateButton.textContent = 'Buscar actualizaciones';
      updateButton.title = 'Comprobar ahora si hay una versión nueva de Phomemo Studio';
      updateButton.onclick = () => {
        if (!post('checkUpdates')) {
          const toast = document.getElementById('toast');
          if (toast) {
            toast.textContent = 'La búsqueda de actualizaciones solo está disponible en la app de escritorio.';
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 2600);
          }
        }
      };
    }

    const syncCard = document.querySelector('.sync-card');
    if (syncCard && !document.getElementById('closeAppWebBtn')) {
      const closeButton = document.createElement('button');
      closeButton.id = 'closeAppWebBtn';
      closeButton.className = 'button ghost';
      closeButton.textContent = 'Cerrar app';
      closeButton.title = 'Cerrar Phomemo Studio';
      closeButton.addEventListener('click', () => post('closeApp'));
      syncCard.appendChild(closeButton);
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireDesktopControls, { once: true });
  } else {
    wireDesktopControls();
  }
})();
