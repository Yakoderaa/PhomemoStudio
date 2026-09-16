(() => {
  'use strict';
  const DPI = 203;
  const PX_PER_MM = DPI / 25.4; // ~7.992
  const PREVIEW_SCALE = 4; // backing canvas HiDPI: preview nÃ­tido sin cambiar coordenadas del diseÃ±o
  const MIN_ELEMENT_SIZE = 4;
  const STORAGE_KEY = 'phomemo_studio_d30_v1';
  const STATE_SCHEMA = 8;
  const REFERENCE_TEMPLATE_ID = 'builtin-12x40-texto-centrado';
  const BLANK_TEMPLATE_ID = 'builtin-12x40-vacia';
  const KINDER_TEMPLATE_ID = 'builtin-12x40-gato-galletas';
  const KINDER_BG = 'assets/kinder_reference_bg_hq.svg';
  const $ = (id) => document.getElementById(id);
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);

  const DEFAULT_STATE = {
    schemaVersion: STATE_SCHEMA,
    groups: ['General', '12Ã—40'],
    templates: [],
    queue: [],
    roll: { name: '12Ã—40 Â· 80 etiquetas', total: 80, remaining: 80 },
    settings: { density: 6, continuous: false, feedDots: 0, autoReconnect: true, autoPowerConnect: true, smoothPrint: true, autoCalibrateNewRoll: false },
    bluetooth: { deviceId: null, deviceName: null },
    printSession: null,
  };

  let state = loadState();
  function makeMainText(text = 'Texto de etiqueta') {
    return { id: uid(), type: 'text', x: 10, y: 10, w: 300, h: 76, text, fontSize: 42, font: 'Bahnschrift SemiCondensed', bold: true, letterSpacing: 0, autoFit: true };
  }
  function makeKinderText(text = 'Kinder bueno\n(rellena)') {
    return { id: uid(), type: 'text', x: 82, y: 8, w: 202, h: 78, text, fontSize: 31, font: 'Segoe Print', bold: true, letterSpacing: -0.25, autoFit: true };
  }
  function makeKinderElements(text = 'Kinder bueno\n(rellena)') {
    return [
      { id: uid(), type: 'image', x: 0, y: 0, w: 320, h: 96, image: KINDER_BG, locked: true, role: 'background' },
      makeKinderText(text),
    ];
  }

  const initialKinderElements = makeKinderElements();
  let editor = {
    widthMm: 40,
    heightMm: 12,
    elements: initialKinderElements,
    selectedId: initialKinderElements.find(e=>e.type==='text')?.id || null,
    templateId: KINDER_TEMPLATE_ID,
    templateName: 'Base 12Ã—40 Â· gato + galletas',
    templateGroup: '12Ã—40',
  };
  let drag = null;
  let printer = null;
  let printing = false;
  let toastTimer = null;

  const canvas = $('labelCanvas');
  const ctx = canvas.getContext('2d', { willReadFrequently: true });

  function loadState() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
      const merged = {
        ...structuredClone(DEFAULT_STATE),
        ...parsed,
        roll: { ...DEFAULT_STATE.roll, ...(parsed?.roll || {}) },
        settings: { ...DEFAULT_STATE.settings, ...(parsed?.settings || {}) },
        bluetooth: { ...DEFAULT_STATE.bluetooth, ...(parsed?.bluetooth || {}) },
        printSession: parsed?.printSession || null,
      };
      // V1.4 migration: las versiones anteriores suponÃ­an rollos de 160.
      // Si el usuario no habÃ­a cambiado ese valor, conservamos las etiquetas ya
      // consumidas pero corregimos la capacidad real a 80.
      if ((parsed?.schemaVersion || 0) < STATE_SCHEMA && +parsed?.roll?.total === 160) {
        const oldRemaining = Number.isFinite(+parsed?.roll?.remaining) ? +parsed.roll.remaining : 160;
        const used = Math.max(0, 160 - oldRemaining);
        merged.roll.total = 80;
        merged.roll.remaining = Math.max(0, 80 - used);
        merged.roll.name = '12Ã—40 Â· 80 etiquetas';
      }
      merged.schemaVersion = STATE_SCHEMA;
      return merged;
    } catch { return structuredClone(DEFAULT_STATE); }
  }
  function saveState() { state.schemaVersion = STATE_SCHEMA; localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }

  function ensureReferenceTemplate() {
    if (!state.groups.includes('12Ã—40')) state.groups.push('12Ã—40');
    // V1.6: upgrade every saved copy of the themed template to the cleaner
    // vector artwork while preserving the user's editable text and layout.
    for (const t of state.templates) {
      for (const e of (t.elements || [])) {
        if (e.type === 'image' && e.image === 'assets/kinder_reference_bg.png') e.image = KINDER_BG;
      }
    }
    if (!state.templates.some(t => t.id === REFERENCE_TEMPLATE_ID)) {
      state.templates.push({
        id: REFERENCE_TEMPLATE_ID,
        name: 'Base 12Ã—40 Â· texto centrado',
        group: '12Ã—40',
        widthMm: 40,
        heightMm: 12,
        elements: [makeMainText('Texto de etiqueta')],
      });
    }
    if (!state.templates.some(t => t.id === BLANK_TEMPLATE_ID)) {
      state.templates.unshift({
        id: BLANK_TEMPLATE_ID,
        name: 'Base 12Ã—40 Â· vacÃ­a',
        group: '12Ã—40',
        widthMm: 40,
        heightMm: 12,
        elements: [],
      });
    }
    const themed = {
      id: KINDER_TEMPLATE_ID,
      name: 'Base 12Ã—40 Â· gato + galletas',
      group: '12Ã—40',
      widthMm: 40,
      heightMm: 12,
      elements: makeKinderElements('Kinder bueno\n(rellena)'),
    };
    const themedIndex = state.templates.findIndex(t => t.id === KINDER_TEMPLATE_ID);
    if (themedIndex >= 0) state.templates[themedIndex] = themed;
    else state.templates.unshift(themed);
    saveState();
  }
  ensureReferenceTemplate();
  function toast(msg) {
    const el = $('toast'); el.textContent = msg; el.classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
  }
  function mmToPx(mm) { return Math.round(mm * PX_PER_MM); }
  function logicalCanvasWidth(){ return mmToPx(editor.widthMm); }
  function logicalCanvasHeight(){ return mmToPx(editor.heightMm); }
  function setCanvasSize() {
    const w = logicalCanvasWidth(), h = logicalCanvasHeight();
    if (canvas.width !== w * PREVIEW_SCALE) canvas.width = w * PREVIEW_SCALE;
    if (canvas.height !== h * PREVIEW_SCALE) canvas.height = h * PREVIEW_SCALE;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    $('sizeText').textContent = (editor.widthMm===40&&editor.heightMm===12) ? 'Papel 12 Ã— 40 mm Â· lienzo 40 Ã— 12' : `${editor.widthMm} Ã— ${editor.heightMm} mm`;
    const val = `${editor.widthMm}x${editor.heightMm}`;
    if ([...$('labelSizeSelect').options].some(o => o.value === val)) $('labelSizeSelect').value = val;
  }

  function renderEditor() {
    setCanvasSize();
    const w = logicalCanvasWidth(), h = logicalCanvasHeight();
    ctx.setTransform(PREVIEW_SCALE,0,0,PREVIEW_SCALE,0,0);
    renderDesign(ctx, w, h, editor.elements, true, editor.selectedId);
    updateProperties();
  }

  function renderDesign(targetCtx, width, height, elements, selection = false, selectedId = null) {
    targetCtx.save();
    targetCtx.imageSmoothingEnabled = true;
    targetCtx.imageSmoothingQuality = 'high';
    targetCtx.clearRect(0,0,width,height);
    targetCtx.fillStyle = '#fff'; targetCtx.fillRect(0,0,width,height);
    targetCtx.lineCap = 'round';
    for (const el of elements) {
      targetCtx.save();
      if (el.type === 'text') {
        targetCtx.fillStyle = '#000';
        targetCtx.textBaseline = 'middle'; targetCtx.textAlign = 'center';
        fitText(targetCtx, el);
      } else if (el.type === 'rect') {
        targetCtx.strokeStyle = '#000'; targetCtx.lineWidth = el.stroke || 2;
        targetCtx.strokeRect(el.x, el.y, el.w, el.h);
      } else if (el.type === 'line') {
        targetCtx.strokeStyle = '#000'; targetCtx.lineWidth = el.stroke || 2;
        targetCtx.beginPa²È="24¡Ì¤ì(€€€€€¥˜ …Ñ¡¥Ì¹½¹¹•Ñ•¥Ñ¡É½Ü¹•ÜÉÉ½È¡Ìü¹µ•ÍÍ…•ñð1„ÌÀÑ½‘…Ûµ„¹¼É•ÍÁ½¹‘§Ì¸œ¤íÑ¡¥Ì¹ÍÑ…ÉÑMÑ…ÑÕÍ5½¹¥Ñ½È ¤íÉ•ÑÕÉ¸ÑÉÕ”ì(€€€ô(€€€…Íå¹Œ‘¥Í½¹¹•Ð ¥ì(€€€€€Ñ¡¥Ì¹µ…¹Õ…±¥Í½¹¹•ÐõÑÉÕ”íÑ¡¥Ì¹…¹•±I•½¹¹•Ð ¤íÑ¡¥Ì¹ÍÑ½ÁMÑ…ÑÕÍ5½¹¥Ñ½È ¤ì(€€€€€ÑÉåí…Ý…¥ÐÑ¡¥Ì¹…±±)Í½¸ ¥Í½¹¹•Ðœ±™…±Í”¤íõ…Ñ¡íô(€€€€€Ñ¡¥Ì¹½¹¹•Ñ•õ™…±Í”íÑ¡¥Ì¹ÝÉ¥Ñ•¡…Èõ¹Õ±°íÑ¡¥Ì¹½¹¥Í½¹¹•Ðü¸¡íµ…¹Õ…°éÑÉÕ•ô¤íÕÁ‘…Ñ•AÉ¥¹Ñ•ÉU$ ¤ì(€€€ô(€€€…Íå¹ŒÍ•¹¡‰åÑ•Ì¥ì(€€€€€¥˜ …Ñ¡¥Ì¹½¹¹•Ñ•¥…Ý…¥ÐÑ¡¥Ì¹É•½¹¹•Ñ9½Ü ¤ì(€€€€€½¹ÍÐ‘…Ñ„õ‰åÑ•Ì¥¹ÍÑ…¹•½˜U¥¹ÐáÉÉ…äý‰åÑ•Ìé¹•ÜU¥¹ÐáÉÉ…ä¡‰åÑ•Ì¤ì(€€€€€±•Ð‰¥¸ôœœí™½È¡±•Ð¤ôÀí¤ñ‘…Ñ„¹±•¹Ñ í¤¬¬¥‰¥¸¬õMÑÉ¥¹œ¹™É½µ¡…É½‘”¡‘…Ñ…m¥t¤ì(€€€€€½¹ÍÐÌõ…Ý…¥ÐÑ¡¥Ì¹…±±)Í½¸ M•¹‘	…Í”ØÐœ±‰Ñ½„¡‰¥¸¤¤ì(€€€€€¥˜¡Ìü¹½¬ôôõ™…±Í•ññÌü¹½¹¹•Ñ•ôôõ™…±Í”¥íÑ¡¥Ì¹½¹¹•Ñ•õ™…±Í”íÑ¡É½Ü¹•ÜÉÉ½È¡Ìü¹µ•ÍÍ…•ñð%µÁÉ•Í½É„‘•Í½¹•Ñ…‘„œ¤íô(€€€ô(€€€ÍÑ½ÁMÑ…ÑÕÍ5½¹¥Ñ½È ¥í¥˜¡Ñ¡¥Ì¹ÍÑ…ÑÕÍQ¥µ•È¥í±•…É%¹Ñ•ÉÙ…°¡Ñ¡¥Ì¹ÍÑ…ÑÕÍQ¥µ•È¤íÑ¡¥Ì¹ÍÑ…ÑÕÍQ¥µ•Èõ¹Õ±°íõ¥˜¡Ñ¡¥Ì¹ÍÑ…ÑÕÍ-¥­Q¥µ•È¥í±•…ÉQ¥µ•½ÕÐ¡Ñ¡¥Ì¹ÍÑ…ÑÕÍ-¥­Q¥µ•È¤íÑ¡¥Ì¹ÍÑ…ÑÕÍ-¥­Q¥µ•Èõ¹Õ±°íõô(€€€ÍÑ…ÉÑMÑ…ÑÕÍ5½¹¥Ñ½È ¥ì(€€€€€Ñ¡¥Ì¹ÍÑ½ÁMÑ…ÑÕÍ5½¹¥Ñ½È ¤ì(€€€€€Ñ¡¥Ì¹ÍÑ…ÑÕÍ-¥­Q¥µ•ÈõÍ•ÑQ¥µ•½ÕÐ  ¤ôùÑ¡¥Ì¹ÅÕ•Éå	…ÑÑ•Éå¹‘A…Á•È¡ÑÉÕ”¤¹…Ñ   ¤ôùíô¤°ÄØÀÀ¤ì(€€€€€Ñ¡¥Ì¹ÍÑ…ÑÕÍQ¥µ•ÈõÍ•Ñ%¹Ñ•ÉÙ…°  ¤ôùÑ¡¥Ì¹ÅÕ•Éå	…ÑÑ•Éå¹‘A…Á•È¡ÑÉÕ”¤¹…Ñ   ¤ôùíô¤°ØÀÀÀÀ¤ì(€€€ô(€€€…Íå¹ŒÅÕ•Éå	…ÑÑ•Éå¹‘A…Á•È¡ÅÕ¥•Ðõ™…±Í”¥ì(€€€€€ÑÉåí½¹ÍÐÌõ…Ý…¥ÐÑ¡¥Ì¹…±±)Í½¸ EÕ•ÉåMÑ…ÑÕÌœ¤íÑ¡¥Ì¹…ÁÁ±åM¹…ÁÍ¡½Ð¡Ì¤íÉ•ÑÕÉ¸Ñ¡¥Ì¹¥¹™¼íô(€€€€€…Ñ ¡”¥í¥˜ …ÅÕ¥•Ð¥Ñ¡É½Ü”íÉ•ÑÕÉ¸Ñ¡¥Ì¹¥¹™¼íô(€€€ô(€€€…Íå¹ŒÅÕ•ÉåMÑ…ÑÕÌ ¥íÉ•ÑÕÉ¸Ñ¡¥Ì¹ÅÕ•Éå	…ÑÑ•Éå¹‘A…Á•È¡™…±Í”¤íô(€€€…Íå¹Œ…±¥‰É…Ñ•I½±°¡Ý¥‘Ñ¡5´ôÐÀ±¡•¥¡Ñ5´ôÄÈ¥ì(€€€€€¥˜ …Ñ¡¥Ì¹½¹¹•Ñ•¥…Ý…¥ÐÑ¡¥Ì¹É•½¹¹•Ñ9½Ü ¤ì(€€€€€½¹ÍÐ±½¥…±\õµµQ½Aà¡Ý¥‘Ñ¡5´¤±±½¥…± õµµQ½Aà¡¡•¥¡Ñ5´¤ì(€€€€€½¹ÍÐÍÉ]¥‘Ñ¡	åÑ•Ìõ5…Ñ ¹•¥°¡±½¥…±\¼à¤±‰±…¹¬õ¹•ÜU¥¹ÐáÉÉ…ä¡ÍÉ]¥‘Ñ¡	åÑ•Ì©±½¥…± ¤ì(€€€€€½¹ÍÐÉ½Ñ…Ñ•õÉ½Ñ…Ñ•I…ÍÑ•ÈäÁ\¡‰±…¹¬±ÍÉ]¥‘Ñ¡	åÑ•Ì±±½¥…± ¤ì(€€€€€½¹ÍÐ¡•…‘•Èõ¹•ÜU¥¹ÐáÉÉ…ä¡lÁàÅ˜°ÁàÄÄ°ÁàÈÐ°ÁàÀÀ°ÁàÅˆ°ÁàÐÀ°ÁàÅ°ÁàÜØ°ÁàÌÀ°ÁàÀÀ±É½Ñ…Ñ•¹Ý¥‘Ñ¡	åÑ•Ì˜ÈÔÔ°¡É½Ñ…Ñ•¹Ý¥‘Ñ¡	åÑ•Ìøøà¤˜ÈÔÔ±É½Ñ…Ñ•¹¡•¥¡Ñ1¥¹•Ì˜ÈÔÔ°¡É½Ñ…Ñ•¹¡•¥¡Ñ1¥¹•Ìøøà¤˜ÈÔÕt¤ì(€€€€€…Ý…¥ÐÑ¡¥Ì¹Í•¹¡¡•…‘•È¤í…Ý…¥ÐÍ±••À ÌÀ¤ì(€€€€€™½È¡±•Ð¤ôÀí¤ñÉ½Ñ…Ñ•¹‘…Ñ„¹±•¹Ñ í¤¬ôÄÈà¥í…Ý…¥ÐÑ¡¥Ì¹Í•¹¡É½Ñ…Ñ•¹‘…Ñ„¹Í±¥”¡¤±5…Ñ ¹µ¥¸¡¤¬ÄÈà±É½Ñ…Ñ•¹‘…Ñ„¹±•¹Ñ ¤¤¤í…Ý…¥ÐÍ±••À Äà¤íô(€€€€€…Ý…¥ÐÍ±••À ÄÄÀÀ¤íÉ•ÑÕÉ¸ÑÉÕ”ì(€€€ô(€€€…Íå¹ŒÁÉ¥¹Ñ•Í¥¸¡‘•Í¥¸±Í•ÑÑ¥¹Ì¥ì(€€€€€¥˜ …Ñ¡¥Ì¹½¹¹•Ñ•¥…Ý…¥ÐÑ¡¥Ì¹É•½¹¹•Ñ9½Ü ¤ì(€€€€€…Ý…¥Ð•¹ÍÕÉ••Í¥¹%µ…•Ì¡‘•Í¥¸¹•±•µ•¹ÑÌ¤ì(€€€€€½¹ÍÐÜõµµQ½Aà¡‘•Í¥¸¹Ý¥‘Ñ¡5´¤± õµµQ½Aà¡‘•Í¥¸¹¡•¥¡Ñ5´¤ì(€€€€€½¹ÍÐÍ…±”õÍ•ÑÑ¥¹Ì¹Íµ½½Ñ¡AÉ¥¹Ðôôõ™…±Í”üÄèàì(€€€€€½¹ÍÐ½™˜õ‘½Õµ•¹Ð¹É•…Ñ•±•µ•¹Ð …¹Ù…Ìœ¤í½™˜¹Ý¥‘Ñ õÜ©Í…±”í½™˜¹¡•¥¡Ðõ ©Í…±”ì(€€€€€½¹ÍÐŒõ½™˜¹•Ñ½¹Ñ•áÐ œÉœ±íÝ¥±±I•…‘É•ÅÕ•¹Ñ±äéÑÉÕ•ô¤íŒ¹¥µ…•Mµ½½Ñ¡¥¹¹…‰±•õÑÉÕ”íŒ¹¥µ…•Mµ½½Ñ¡¥¹EÕ…±¥Ñäô¡¥ œíŒ¹Í…±”¡Í…±”±Í…±”¤ì(€€€€€É•¹‘•É•Í¥¸¡Œ±Ü± ±‘•Í¥¸¹•±•µ•¹ÑÌ±™…±Í”±¹Õ±°¤ì(€€€€€½¹ÍÐÉ…ÍÑ•ÈõÍ…±”ôôôÄý…¹Ù…ÍQ½I…ÍÑ•È¡Œ±Ü± ¤éÍÕÁ•ÉÍ…µÁ±•‘…¹Ù…ÍQ½I…ÍÑ•È¡½™˜±Ü± ±Í…±”¤ì(€€€€€½¹ÍÐÉ½Ñ…Ñ•õÉ½Ñ…Ñ•I…ÍÑ•ÈäÁ\¡É…ÍÑ•È¹‘…Ñ„±É…ÍÑ•È¹Ý¥‘Ñ¡	åÑ•Ì± ¤ì(€€€€€±•ÐÁÉ¥¹Ñ…Ñ„õÉ½Ñ…Ñ•¹‘…Ñ„±É½ÝÌõÉ½Ñ…Ñ•¹¡•¥¡Ñ1¥¹•Ìì(€€€€€¥˜¡Í•ÑÑ¥¹Ì¹½¹Ñ¥¹Õ½ÕÌ˜™Í•ÑÑ¥¹Ì¹™••‘½ÑÌøÀ¥í½¹ÍÐÁ…‘I½ÝÌôÔØ­Í•ÑÑ¥¹Ì¹™••‘½ÑÌí½¹ÍÐÁ…‘‘•õ¹•ÜU¥¹ÐáÉÉ…ä¡ÁÉ¥¹Ñ…Ñ„¹±•¹Ñ ­Á…‘I½ÝÌ©É½Ñ…Ñ•¹Ý¥‘Ñ¡	åÑ•Ì¤íÁ…‘‘•¹Í•Ð¡ÁÉ¥¹Ñ…Ñ„¤íÁÉ¥¹Ñ…Ñ„õÁ…‘‘•íÉ½ÝÌ¬õÁ…‘I½ÝÌíô(€€€€€½¹ÍÐ¡•…ÐõlÐÀ°ØÀ°àÀ°ÄÀÀ°ÄÈÀ°ÄÐÀ°ÄØÀ°ÈÀÁum5…Ñ ¹µ…à À±5…Ñ ¹µ¥¸ Ü°¡Í•ÑÑ¥¹Ì¹‘•¹Í¥ÑåñðØ¤´Ä¤¥tì(€€€€€…Ý…¥ÐÑ¡¥Ì¹Í•¹¡¹•ÜU¥¹ÐáÉÉ…ä¡lÁàÅˆ°ÁàÌÜ°ÁàÀÜ±¡•…Ð°ÁàÀÉt¤¤í…Ý…¥ÐÍ±••À ÈÔ¤ì(€€€€€…Ý…¥ÐÑ¡¥Ì¹Í•¹¡¹•ÜU¥¹ÐáÉÉ…ä¡lÁàÅ˜°ÁàÄÄ±Í•ÑÑ¥¹Ì¹½¹Ñ¥¹Õ½ÕÌüÁàÁˆèÁàÁ…t¤¤í…Ý…¥ÐÍ±••À ÈÔ¤ì(€€€€€…Ý…¥ÐÑ¡¥Ì¹Í•¹¡¹•ÜU¥¹ÐáÉÉ…ä¡lÁàÅˆ°ÁàÐÀ°ÁàÅ°ÁàÜØ°ÁàÌÀ°ÁàÀÀ±É½Ñ…Ñ•¹Ý¥‘Ñ¡	åÑ•Ì˜ÈÔÔ°¡É½Ñ…Ñ•¹Ý¥‘Ñ¡	åÑ•Ìøøà¤˜ÈÔÔ±É½ÝÌ˜ÈÔÔ°¡É½ÝÌøøà¤˜ÈÔÕt¤¤ì(€€€€€™½È¡±•Ð¤ôÀí¤ñÁÉ¥¹Ñ…Ñ„¹±•¹Ñ í¤¬ôÄÈà¥í…Ý…¥ÐÑ¡¥Ì¹Í•¹¡ÁÉ¥¹Ñ…Ñ„¹Í±¥”¡¤±5…Ñ ¹µ¥¸¡¤¬ÄÈà±ÁÉ¥¹Ñ…Ñ„¹±•¹Ñ ¤¤¤í…Ý…¥ÐÍ±••À ÈÀ¤íô(€€€€€…Ý…¥ÐÍ±••À äÀ¤í…Ý…¥ÐÑ¡¥Ì¹Í•¹¡¹•ÜU¥¹ÐáÉÉ…ä¡lÁàÅˆ°ÁàØÐ°ÁàÀÁt¤¤í…Ý…¥ÐÍ±••À ÄÈÀ¤ì(€€€ô(€ô((€ÁÉ¥¹Ñ•È€ô¹•ÜÌÁAÉ¥¹Ñ•È ¤ì(€ÁÉ¥¹Ñ•È¹Í•ÑÕÑ½I•½¹¹•Ð¡ÍÑ…Ñ”¹Í•ÑÑ¥¹Ì¹…ÕÑ½I•½¹¹•Ð„ôõ™…±Í”¤ì(€ÁÉ¥¹Ñ•È¹Í•ÑÕÑ½A½Ý•É½¹¹•Ð¡ÍÑ…Ñ”¹Í•ÑÑ¥¹Ì¹…ÕÑ½A½Ý•É½¹¹•Ð„ôõ™…±Í”¤ì(€Ý¥É•AÉ¥¹Ñ•É…±±‰…­Ì ¤ì((€…Íå¹Œ™Õ¹Ñ¥½¸É•ÍÑ½É•AÉ¥¹Ñ•ÉM•ÍÍ¥½¸ ¥ì(€€€¥˜¡ÍÑ…Ñ”¹Í•ÑÑ¥¹Ì¹…ÕÑ½I•½¹¹•Ðôôõ™…±Í”˜™ÍÑ…Ñ”¹Í•ÑÑ¥¹Ì¹…ÕÑ½A½Ý•É½¹¹•Ðôôõ™…±Í”¥É•ÑÕÉ¸ì(€€€½¹ÍÐ½¬õ…Ý…¥ÐÁÉ¥¹Ñ•È¹É•ÍÑ½É•-¹½Ý¹•Ù¥” ¤ì(€€€ÕÁ‘…Ñ•AÉ¥¹Ñ•ÉU$ ¤ì(€€€¥˜¡½¬¥Ñ½…ÍÐ ÌÀ½¹•Ñ…‘„…ÕÑ½·…Ñ¥…µ•¹Ñ”œ¤ì(€€€•±Í”¥˜¡ÍÑ…Ñ”¹‰±Õ•Ñ½½Ñ ü¹‘•Ù¥•%‘ññÍÑ…Ñ”¹‰±Õ•Ñ½½Ñ ü¹‘•Ù¥•9…µ”¥íÍ•Ñ	Ñ¥…¹½ÍÑ¥Œ ÌÀÉ•½É‘…‘„ƒ
Ü•ÍÁ•É…¹‘¼„ÅÕ”Í”•¹¥•¹‘‡Š˜œ¤íÁÉ¥¹Ñ•È¹ÍÑ…ÉÑAÉ•Í•¹•]…Ñ¡•È ¤íô(€ô((€…Íå¹Œ™Õ¹Ñ¥½¸•¹ÍÕÉ••Í¥¹%µ…•Ì¡•±•µ•¹ÑÌ¥ì(€€€½¹ÍÐÍ½ÕÉ•Ìõ•±•µ•¹ÑÌ¹™¥±Ñ•È¡”ôù”¹ÑåÁ”ôôô¥µ…”œ˜™”¹¥µ…”¤¹µ…À¡”ôù”¹¥µ…”¤ì(€€€…Ý…¥ÐAÉ½µ¥Í”¹…±°¡Í½ÕÉ•Ì¹µ…À¡ÍÉŒôù¹•ÜAÉ½µ¥Í”¡É•Í½±Ù”ôùí½¹ÍÐ¥µœõ•Ñ…¡•‘%µ…”¡ÍÉŒ¤í¥˜¡¥µœ¹½µÁ±•Ñ”¥É•ÑÕÉ¸É•Í½±Ù” ¤í½¹ÍÐ‘½¹”ô ¤ôùÉ•Í½±Ù” ¤í¥µœ¹…‘‘Ù•¹Ñ1¥ÍÑ•¹•È ±½…œ±‘½¹”±í½¹”éÑÉÕ•ô¤í¥µœ¹…‘‘Ù•¹Ñ1¥ÍÑ•¹•È •ÉÉ½Èœ±‘½¹”±í½¹”éÑÉÕ•ô¤íô¤¤¤ì(€ô((€™Õ¹Ñ¥½¸…¹Ù…ÍQ½I…ÍÑ•È¡Œ±Ü± ¥í½¹ÍÐ¥´õŒ¹•Ñ%µ…•…Ñ„ À°À±Ü± ¤¹‘…Ñ„±Ý¥‘Ñ¡	åÑ•Ìõ5…Ñ ¹•¥°¡Ü¼à¤±½ÕÐõ¹•ÜU¥¹ÐáÉÉ…ä¡Ý¥‘Ñ¡	åÑ•Ì© ¤í™½È¡±•ÐäôÀíäñ íä¬¬¥í™½È¡±•ÐàôÀíàñÜíà¬¬¥í½¹ÍÐ¤ô¡ä©Ü­à¤¨Ðí½¹ÍÐ±Õ´ôÀ¸Èää©¥µm¥t¬À¸ÔàÜ©¥µm¤¬Åt¬À¸ÄÄÐ©¥µm¤¬Étí¥˜¡¥µm¤¬ÍtøÌÈ˜™±Õ´ðÄØÀ¥½ÕÑmä©Ý¥‘Ñ¡	åÑ•Ì¬¡àøøÌ¥uðô ÁààÀøø¡à˜Ü¤¤íõõÉ•ÑÕÉ¹í‘…Ñ„é½ÕÐ±Ý¥‘Ñ¡	åÑ•Íôíô(€™Õ¹Ñ¥½¸ÍÕÁ•ÉÍ…µÁ±•‘…¹Ù…ÍQ½I…ÍÑ•È¡…¹Ù…Ì±Ü± ±Í…±”¥ì(€€€½¹ÍÐŒõ…¹Ù…Ì¹•Ñ½¹Ñ•áÐ œÉœ±íÝ¥±±I•…‘É•ÅÕ•¹Ñ±äéÑÉÕ•ô¤ì(€€€½¹ÍÐ¥´õŒ¹•Ñ%µ…•…Ñ„ À°À±…¹Ù…Ì¹Ý¥‘Ñ ±…¹Ù…Ì¹¡•¥¡Ð¤¹‘…Ñ„ì(€€€½¹ÍÐÝ¥‘Ñ¡	åÑ•Ìõ5…Ñ ¹•¥°¡Ü¼à¤±½ÕÐõ¹•ÜU¥¹ÐáÉÉ…ä¡Ý¥‘Ñ¡	åÑ•Ì© ¤ì(€€€½¹ÍÐ¸õÍ…±”©Í…±”ì(€€€™½È¡±•ÐäôÀíäñ íä¬¬¥ì(€€€€€™½È¡±•ÐàôÀíàñÜíà¬¬¥ì(€€€€€€€±•Ð¥¹¬ôÀì(€€€€€€€™½È¡±•ÐÍäôÀíÍäñÍ…±”íÍä¬¬¥™½È¡±•ÐÍàôÀíÍàñÍ…±”íÍà¬¬¥ì(€€€€€€€€€½¹ÍÐÁàõà©Í…±”­Íà±Áäõä©Í…±”­Íä±¤ô¡Áä©…¹Ù…Ì¹Ý¥‘Ñ ­Áà¤¨Ðì(€€€€€€€€€½¹ÍÐ±Õ´ôÀ¸Èää©¥µm¥t¬À¸ÔàÜ©¥µm¤¬Åt¬À¸ÄÄÐ©¥µm¤¬Étì(€€€€€€€€€¥¹¬€¬ô€ ÈÔÔµ±Õ´¤€¨€¡¥µm¤¬Ít¼ÈÔÔ¤ì(€€€€€€€ô(€€€€€€€½¹ÍÐ½Ù•É…”õ¥¹¬¼ ÈÔÔ©¸¤ì(€€€€€€€€¼¼1¥¹”µ…ÉÐµ½‘”è¹¼½É‘•É•‘¥Ñ¡•É¥¹œ¸½Ù•É…”Ñ¡É•Í¡½±¥Ù•Ì±•…¸°(€€€€€€€€¼¼ÍÑ…‰±”•‘•Ì…ÐÑ¡”ÌÀÌ¹…Ñ¥Ù”€ÈÀÌ‘Á¤¥¹ÍÑ•…½˜„¹½¥ÍäÍ…ÜÁ…ÑÑ•É¸¸(€€€€€€€¥˜¡½Ù•É…”øôÀ¸ÈÜ¥½ÕÑmä©Ý¥‘Ñ¡	åÑ•Ì¬¡àøøÌ¥uðô ÁààÀøø¡à˜Ü¤¤ì(€€€€€ô(€€€ô(€€€É•ÑÕÉ¹í‘…Ñ„é½ÕÐ±Ý¥‘Ñ¡	åÑ•Íôì(€ô(€™Õ¹Ñ¥½¸É½Ñ…Ñ•I…ÍÑ•ÈäÁ\¡‘…Ñ„±Ý¥‘Ñ¡	åÑ•Ì±¡•¥¡Ñ1¥¹•Ì¥í½¹ÍÐÍÉ\õÝ¥‘Ñ¡	åÑ•Ì¨à±ÍÉ õ¡•¥¡Ñ1¥¹•Ì±‘ÍÑ\õÍÉ ±‘ÍÑ õÍÉ\±‘ÍÑ]¥‘Ñ¡	åÑ•Ìõ5…Ñ ¹•¥°¡‘ÍÑ\¼à¤±½ÕÐõ¹•ÜU¥¹ÐáÉÉ…ä¡‘ÍÑ]¥‘Ñ¡	åÑ•Ì©‘ÍÑ ¤í™½È¡±•ÐäôÀíäñÍÉ íä¬¬¥í™½È¡±•ÐàôÀíàñÍÉ\íà¬¬¥í¥˜¡‘…Ñ…mä©Ý¥‘Ñ¡	åÑ•Ì¬¡àøøÌ¥t˜ ÁààÀøø¡à˜Ü¤¤¥í½¹ÍÐ‘àõÍÉ ´Äµä±‘äõàí½ÕÑm‘ä©‘ÍÑ]¥‘Ñ¡	åÑ•Ì¬¡‘àøøÌ¥uðô ÁààÀøø¡‘à˜Ü¤¤íõõõÉ•ÑÕÉ¹í‘…Ñ„é½ÕÐ±Ý¥‘Ñ¡	åÑ•Ìé‘ÍÑ]¥‘Ñ¡	åÑ•Ì±¡•¥¡Ñ1¥¹•Ìé‘ÍÑ!ôíô((€€¼¼XÌ•Í­Ñ½Àè±„¥¹Ñ•É™…èÙ¥Ù”‘•¹ÑÉ¼‘”±„…Á±¥…§Í¸‘”]¥¹‘½ÝÌì¹¼¡…äÍ•ÉÙ¥‘½È¹¤¹…Ù•…‘½È•áÑ•É¹¼¸(€…‘‘Ù•¹Ñ1¥ÍÑ•¹•È ™½ÕÌœ° ¤ôùí¥˜¡ÍÑ…Ñ”¹Í•ÑÑ¥¹Ì¹…ÕÑ½A½Ý•É½¹¹•Ð„ôõ™…±Í”¥ÁÉ¥¹Ñ•Èü¹Ý…­•ÕÑ½½¹¹•Ð ¤íô¤ì(€‘½Õµ•¹Ð¹…‘‘Ù•¹Ñ1¥ÍÑ•¹•È Ù¥Í¥‰¥±¥Ñå¡…¹”œ° ¤ôùí¥˜ …‘½Õµ•¹Ð¹¡¥‘‘•¸˜™ÍÑ…Ñ”¹Í•ÑÑ¥¹Ì¹…ÕÑ½A½Ý•É½¹¹•Ð„ôõ™…±Í”¥ÁÉ¥¹Ñ•Èü¹Ý…­•ÕÑ½½¹¹•Ð ¤íô¤ì((€½¹ÍÐÍÑ…ÉÑÕÁQ•µÁ±…Ñ”õÍÑ…Ñ”¹Ñ•µÁ±…Ñ•Ì¹™¥¹¡ÐôùÐ¹¥ôôõ-%9I}Q5A1Q}%¤í¥˜¡ÍÑ…ÉÑÕÁQ•µÁ±…Ñ”¥í½¹ÍÐ•±•µ•¹ÑÌõÍÑÉÕÑÕÉ•‘±½¹”¡ÍÑ…ÉÑÕÁQ•µÁ±…Ñ”¹•±•µ•¹ÑÌ¤í½¹ÍÐµ…¥¸õ•±•µ•¹ÑÌ¹™¥¹¡”ôù”¹ÑåÁ”ôôôÑ•áÐœ¤í•‘¥Ñ½ÈõíÝ¥‘Ñ¡5´éÍÑ…ÉÑÕÁQ•µÁ±…Ñ”¹Ý¥‘Ñ¡5´±¡•¥¡Ñ5´éÍÑ…ÉÑÕÁQ•µÁ±…Ñ”¹¡•¥¡Ñ5´±•±•µ•¹ÑÌ±Í•±•Ñ•‘%éµ…¥¸ü¹¥‘ññ¹Õ±°±Ñ•µÁ±…Ñ•%éÍÑ…ÉÑÕÁQ•µÁ±…Ñ”¹¥±Ñ•µÁ±…Ñ•9…µ”éÍÑ…ÉÑÕÁQ•µÁ±…Ñ”¹¹…µ”±Ñ•µÁ±…Ñ•É½ÕÀéÍÑ…ÉÑÕÁQ•µÁ±…Ñ”¹É½ÕÁôíô(€É•¹‘•É‘¥Ñ½È ¤íÉ•¹‘•É1¥‰É…Éä ¤íÉ•¹‘•ÉEÕ•Õ” ¤íÉ•¹‘•ÉI½±° ¤íÕÁ‘…Ñ•AÉ¥¹Ñ•ÉU$ ¤ì(€Í•ÑQ¥µ•½ÕÐ  ¤ôùÉ•ÍÑ½É•AÉ¥¹Ñ•ÉM•ÍÍ¥½¸ ¤°ÜÀÀ¤ì)ô¤ ¤ì