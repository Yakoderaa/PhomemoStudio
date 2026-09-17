(() => {
  'use strict';

  const getToast = () => document.getElementById('toast');

  const toast = (message) => {
    const el = getToast();
    if (!el) return;
    el.textContent = message;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 2800);
  };

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

  const setUpdateUi = (state) => {
    const updateButton = document.getElementById('applePlaceholderBtn');
    const syncCard = document.querySelector('.sync-card');
    const status = syncCard?.querySelector('span');

    if (status && state?.message) status.textContent = state.message;
    if (!updateButton) return;

    updateButton.disabled = !!state?.busy;

    switch (state?.stage) {
      case 'checking':
        updateButton.textContent = 'Buscando…';
        break;
      case 'found':
      case 'downloading':
        updateButton.textContent = state?.percent == null ? 'Descargando…' : `Descargando ${Math.round(state.percent)}%`;
        break;
      case 'verifying':
        updateButton.textContent = 'Verificando…';
        break;
      case 'ready':
        updateButton.textContent = 'Instalando…';
        break;
      case 'installing':
        updateButton.textContent = 'Instalando…';
        break;
      case 'current':
        updateButton.textContent = 'Buscar actualizaciones';
        updateButton.disabled = false;
        toast(state.message || 'Phomemo Studio está al día.');
        break;
      case 'error':
        updateButton.textContent = 'Reintentar actualización';
        updateButton.disabled = false;
        toast(state.message || 'No se pudo actualizar.');
        break;
      default:
        if (!state?.busy) {
          updateButton.textContent = 'Buscar actualizaciones';
          updateButton.disabled = false;
        }
        break;
    }
  };

  const wireDesktopControls = () => {
    const updateButton = document.getElementById('applePlaceholderBtn');
    if (updateButton) {
      updateButton.textContent = 'Buscar actualizaciones';
      updateButton.title = 'Buscar, descargar, instalar y reiniciar Phomemo Studio';
      updateButton.onclick = () => {
        updateButton.disabled = true;
        updateButton.textContent = 'Buscando…';
        const syncCard = document.querySelector('.sync-card');
        const status = syncCard?.querySelector('span');
        if (status) status.textContent = 'Buscando la última versión…';

        if (!post('checkUpdates')) {
          updateButton.disabled = false;
          updateButton.textContent = 'Buscar actualizaciones';
          toast('La búsqueda de actualizaciones solo está disponible en la app de escritorio.');
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

    try {
      window.chrome?.webview?.addEventListener('message', (event) => {
        if (event?.data?.type === 'updateState') setUpdateUi(event.data);
      });
    } catch (e) {
      console.error('desktop update listener failed', e);
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireDesktopControls, { once: true });
  } else {
    wireDesktopControls();
  }
})();
