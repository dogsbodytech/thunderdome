import * as THREE from './vendor/three.module.js';
import { OrbitControls } from './vendor/OrbitControls.js';

export const STRING_COLOURS = ['#ff4040', '#33d17a', '#3584e4', '#f6d32d', '#c061cb'];
export function stringColor(controllerNumber) { return STRING_COLOURS[(Number(controllerNumber) - 1 + STRING_COLOURS.length) % STRING_COLOURS.length]; }
export function validateLedIndex(value, total = 5000) {
  const index = Number(value);
  if (!Number.isInteger(index) || index < 0 || index >= total) return { ok: false, error: `Enter a global LED index from 0 to ${total - 1}.` };
  return { ok: true, index };
}
export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
}
export function formatLedMetadata(led) {
  if (!led) return '<p>Select an LED.</p>';
  const route = led.is_tail ? `tail #${escapeHtml(led.tail_index)}` : `${escapeHtml(led.spar_id || 'unknown spar')} ${escapeHtml(led.from_hub)}→${escapeHtml(led.to_hub)}`;
  return `<h2>LED ${led.global_index}</h2><dl class="kv">
    <dt>Controller</dt><dd>${led.controller_number}</dd>
    <dt>String ID</dt><dd>${led.string_id}</dd>
    <dt>Local index</dt><dd>${led.local_index}</dd>
    <dt>XYZ</dt><dd>${led.xyz.map(v => Number(v).toFixed(3)).join(', ')}</dd>
    <dt>Tail</dt><dd>${led.is_tail ? 'yes' : 'no'}</dd>
    <dt>Route</dt><dd>${route}</dd>
  </dl>`;
}

const state = { metadata: null, geometry: null, leds: [], selectedLed: null, selectedHub: null, cameraMode: 'perspective' };
const objects = {}; let lastLiveFrameAt = 0; let lastLiveSequence = null; let skippedLiveFrames = 0; let reconnectAttempt = 0;
const viewer = document.getElementById('viewer');
const status = document.getElementById('status');
const inspection = document.getElementById('inspection');
const overlayError = document.getElementById('overlay-error');
const raycaster = new THREE.Raycaster();
raycaster.params.Points.threshold = 0.06;
const pointer = { x: 0, y: 0 };

function showError(message) { overlayError.textContent = message; overlayError.classList.remove('hidden'); status.innerHTML = `<p class="error">${message}</p>`; }
async function loadJson(path) {
  const response = await fetch(path, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${path} failed: ${response.status}`);
  try { return await response.json(); } catch (error) { throw new Error(`${path} returned invalid JSON: ${error.message}`); }
}
function colorToRgb(hex) { const n = Number.parseInt(hex.slice(1), 16); return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255]; }
function centreFromBounds(bounds) { return new THREE.Vector3((bounds.x[0]+bounds.x[1])/2, (bounds.y[0]+bounds.y[1])/2, (bounds.z[0]+bounds.z[1])/2); }
function maxSpan(bounds) { return Math.max(bounds.x[1]-bounds.x[0], bounds.y[1]-bounds.y[0], bounds.z[1]-bounds.z[0]); }

const scene = new THREE.Scene();
const renderer = new THREE.WebGLRenderer({ antialias: true });
viewer.appendChild(renderer.domElement);
let perspectiveCamera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
let orthoCamera = new THREE.OrthographicCamera(-4, 4, 4, -4, 0.01, 1000);
perspectiveCamera.up.set(0, 0, 1);
orthoCamera.up.set(0, 0, 1);
let camera = perspectiveCamera;
let controls = new OrbitControls(camera, renderer.domElement);

function resize() {
  const rect = viewer.getBoundingClientRect();
  const width = rect.width || 800;
  const height = rect.height || 600;
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.setSize(width, height);
  perspectiveCamera.aspect = width / height;
  perspectiveCamera.updateProjectionMatrix();
  const span = state.metadata ? maxSpan(state.metadata.bounds) : 8;
  const halfWidth = span * width / height;
  orthoCamera.left = -halfWidth; orthoCamera.right = halfWidth;
  orthoCamera.top = span; orthoCamera.bottom = -span;
  orthoCamera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);

function makeLeds(leds) {
  const positions = new Float32Array(leds.length * 3);
  const colours = new Float32Array(leds.length * 3);
  leds.forEach((led, index) => {
    positions[index*3] = led.xyz[0]; positions[index*3+1] = led.xyz[1]; positions[index*3+2] = led.xyz[2];
    const rgb = colorToRgb(stringColor(led.controller_number));
    colours[index*3] = rgb[0]; colours[index*3+1] = rgb[1]; colours[index*3+2] = rgb[2];
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colours, 3));
  geometry.computeBoundingSphere();
  return new THREE.Points(geometry, new THREE.PointsMaterial({ size: 0.035, vertexColors: true }));
}
function makeSpars(spars) {
  const positions = new Float32Array(spars.length * 6);
  spars.forEach((spar, index) => { positions.set([...spar.start_xyz, ...spar.end_xyz], index * 6); });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: 0x64748b }));
}
function createTextSprite(text, { apex = false } = {}) {
  const canvas = document.createElement('canvas');
  canvas.width = 256; canvas.height = 96;
  const context = canvas.getContext('2d');
  const foreground = apex ? '#fff7a3' : '#e7efff';
  const background = apex ? 'rgba(93, 66, 0, 0.82)' : 'rgba(15, 23, 42, 0.78)';
  context.fillStyle = background;
  context.roundRect(4, 4, canvas.width - 8, canvas.height - 8, 18);
  context.fill();
  context.strokeStyle = apex ? '#facc15' : '#93c5fd';
  context.lineWidth = 4;
  context.roundRect(4, 4, canvas.width - 8, canvas.height - 8, 18);
  context.stroke();
  context.fillStyle = foreground;
  context.font = '600 52px sans-serif';
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  context.fillText(text, canvas.width / 2, canvas.height / 2 + 2);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(apex ? 0.48 : 0.38, apex ? 0.18 : 0.14, 1);
  sprite.raycast = () => {};
  return sprite;
}
function createHubLabel(hub) {
  const sprite = createTextSprite(hub.id, { apex: hub.id === 'H061' });
  sprite.position.set(hub.x, hub.y, hub.z + (hub.id === 'H061' ? 0.10 : 0.06));
  sprite.userData = { kind: 'hub-label', hubId: hub.id };
  return sprite;
}
function makeHubs(hubs) {
  const group = new THREE.Group();
  const positions = new Float32Array(hubs.length * 3);
  const colours = new Float32Array(hubs.length * 3);
  hubs.forEach((hub, index) => { positions.set(hub.xyz, index*3); const rgb = hub.id === 'H061' ? [1, 1, 0] : [0.7,0.8,1]; colours.set(rgb, index*3); });
  const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3)); geometry.setAttribute('color', new THREE.BufferAttribute(colours, 3));
  const points = new THREE.Points(geometry, new THREE.PointsMaterial({ size: 0.07, vertexColors: true })); points.userData.kind = 'hubs'; group.add(points);
  const labels = new THREE.Group(); labels.visible = false;
  hubs.filter(hub => typeof hub.id === 'string' && hub.id).forEach(hub => labels.add(createHubLabel(hub)));
  group.labels = labels; group.points = points; group.add(labels); return group;
}
function makeGround(bounds) { const span = maxSpan(bounds) * 1.2; const mesh = new THREE.Mesh(new THREE.PlaneGeometry(span, span), new THREE.MeshBasicMaterial({ color: 0x111827, side: THREE.DoubleSide })); mesh.position.z = bounds.z[0]; return mesh; }
function makeAxes(bounds) { return new THREE.AxesHelper(maxSpan(bounds) * 0.6); }

function fitView(view='perspective') {
  const bounds = state.metadata.bounds; const c = centreFromBounds(bounds); const span = maxSpan(bounds) || 4;
  const placements = { perspective: [span*0.9, -span*1.4, span*.75], top: [c.x, c.y, c.z + span*1.7], front: [c.x, c.y - span*1.7, c.z], side: [c.x + span*1.7, c.y, c.z], opposite: [c.x - span*1.7, c.y, c.z] };
  const [x,y,z] = placements[view] || placements.perspective; camera.position.set(x,y,z); controls.target.copy(c); controls.update();
}
function switchCamera() {
  state.cameraMode = state.cameraMode === 'perspective' ? 'orthographic' : 'perspective';
  const old = camera;
  camera = state.cameraMode === 'perspective' ? perspectiveCamera : orthoCamera;
  camera.position.copy(old.position);
  controls.dispose();
  controls = new OrbitControls(camera, renderer.domElement);
  fitView('perspective');
}

function updateLedColours() {
  const attr = objects.leds.geometry.attributes.color; const selected = document.getElementById('string-filter').value; const showTails = document.getElementById('show-tails').checked; const highlightTails = document.getElementById('highlight-tails').checked;
  state.leds.forEach((led, index) => {
    let rgb = colorToRgb(stringColor(led.controller_number));
    if (!showTails && led.is_tail) rgb = [0,0,0];
    if (highlightTails) rgb = led.is_tail ? [1,1,1] : [0.05,0.05,0.05];
    if (selected !== 'all' && Number(selected) !== led.controller_number) rgb = rgb.map(v => v * 0.15);
    if (state.selectedLed && state.selectedLed.global_index === led.global_index) rgb = [1,1,1];
    attr.array.set(rgb, index * 3);
  });
  attr.needsUpdate = true;
}
function setHubLabelsVisible(enabled) { objects.hubs.labels.visible = enabled; }
function connectLiveFrames() {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'; const socket = new WebSocket(`${scheme}://${location.host}/ws/viewer`); socket.binaryType = 'arraybuffer';
  socket.onopen = () => { reconnectAttempt = 0; document.getElementById('stream-status').textContent = 'Connected'; };
  socket.onerror = () => socket.close();
  socket.onclose = () => { const delay = Math.min(1000 * 2 ** reconnectAttempt, 30000); reconnectAttempt += 1; document.getElementById('stream-status').textContent = `Disconnected; retrying in ${(delay / 1000).toFixed(0)}s…`; setTimeout(connectLiveFrames, delay); };
  socket.onmessage = event => {
    const bytes = new Uint8Array(event.data); if (bytes.length !== 15032 || String.fromCharCode(...bytes.slice(0,4)) !== 'TDFR' || bytes[4] !== 1) return;
    const view = new DataView(bytes.buffer); const sequence = Number(view.getBigUint64(8)); const attr = objects.leds.geometry.attributes.color;
    if (view.getUint16(6) !== 32 || view.getUint32(24) !== 5000 || view.getUint32(28) !== 15000) return;
    for (let index = 0; index < 5000; index += 1) { const source = 32 + index * 3; attr.array[index * 3] = bytes[source] / 255; attr.array[index * 3 + 1] = bytes[source + 1] / 255; attr.array[index * 3 + 2] = bytes[source + 2] / 255; }
    attr.needsUpdate = true; const now = performance.now(); if (lastLiveFrameAt) document.getElementById('stream-fps').textContent = (1000 / (now - lastLiveFrameAt)).toFixed(1); if (lastLiveSequence !== null && sequence > lastLiveSequence + 1) { skippedLiveFrames += sequence - lastLiveSequence - 1; document.getElementById('stream-skipped').textContent = skippedLiveFrames; } lastLiveFrameAt = now; lastLiveSequence = sequence; document.getElementById('stream-sequence').textContent = sequence;
  };
}
function updateToggles() { objects.leds.visible = document.getElementById('show-leds').checked; objects.spars.visible = document.getElementById('show-spars').checked; objects.hubs.visible = document.getElementById('show-hubs').checked; objects.ground.visible = document.getElementById('show-ground').checked; objects.axes.visible = document.getElementById('show-axes').checked; setHubLabelsVisible(document.getElementById('show-labels').checked); updateLedColours(); }
function selectLed(index) { state.selectedLed = state.leds[index]; state.selectedHub = null; inspection.innerHTML = formatLedMetadata(state.selectedLed); updateLedColours(); }
function selectHub(index) { const hub = state.geometry.hubs[index]; state.selectedHub = hub; state.selectedLed = null; inspection.innerHTML = `<h2>Hub ${hub.id}</h2><dl class="kv"><dt>XYZ</dt><dd>${hub.xyz.map(v=>Number(v).toFixed(3)).join(', ')}</dd><dt>Apex</dt><dd>${hub.is_apex ? 'yes' : 'no'}</dd></dl>`; }

async function init() {
  try {
    const [metadata, geometry, ledPayload] = await Promise.all([loadJson('/api/simulator/metadata'), loadJson('/api/simulator/geometry'), loadJson('/api/simulator/leds')]);
    if (!Array.isArray(ledPayload.leds) || ledPayload.leds.length !== 5000) throw new Error(`Unexpected LED count: ${ledPayload.leds?.length}`);
    state.metadata = metadata; state.geometry = geometry; state.leds = ledPayload.leds;
    status.innerHTML = `<dl class="kv"><dt>LEDs</dt><dd>${metadata.total_led_count}</dd><dt>Tails</dt><dd>${metadata.tail_count}</dd><dt>Strings</dt><dd>${metadata.string_count}</dd><dt>Hubs</dt><dd>${metadata.hub_count}</dd><dt>Spars</dt><dd>${metadata.spar_count}</dd></dl>`;
    objects.spars = makeSpars(geometry.spars); objects.leds = makeLeds(state.leds); objects.hubs = makeHubs(geometry.hubs); objects.ground = makeGround(metadata.bounds); objects.axes = makeAxes(metadata.bounds);
    scene.add(objects.ground, objects.spars, objects.leds, objects.hubs, objects.axes); resize(); fitView('perspective'); updateToggles(); connectLiveFrames(); animate();
  } catch (error) { showError(`Simulator failed to load.\n${error.message}\nConfirm local vendor files and API endpoints are available.`); }
}
function animate() { requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); }

viewer.addEventListener('click', event => {
  const rect = renderer.domElement.getBoundingClientRect(); pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1; pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1; raycaster.setFromCamera(pointer, camera);
  const ledHit = raycaster.intersectObject(objects.leds || {})[0]; if (ledHit) { selectLed(ledHit.index); return; }
  const hubHit = raycaster.intersectObject(objects.hubs?.points || {})[0]; if (hubHit) selectHub(hubHit.index);
});
document.getElementById('lookup-form').addEventListener('submit', event => { event.preventDefault(); const input = document.getElementById('led-index'); const result = validateLedIndex(input.value, state.leds.length || 5000); document.getElementById('lookup-error').textContent = result.ok ? '' : result.error; if (result.ok) selectLed(result.index); });
for (const id of ['show-leds','show-spars','show-hubs','show-tails','highlight-tails','show-ground','show-axes','show-labels','string-filter']) document.getElementById(id).addEventListener('change', updateToggles);
for (const button of document.querySelectorAll('button[data-view]')) button.addEventListener('click', () => fitView(button.dataset.view));
document.getElementById('toggle-camera').addEventListener('click', switchCamera);
document.getElementById('fit-view').addEventListener('click', () => fitView('perspective'));
document.getElementById('reset-view').addEventListener('click', () => fitView('perspective'));
document.getElementById('restore-diagnostics').addEventListener('click', updateLedColours);
init();
