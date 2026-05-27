import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createUnitObject } from '../objects/index.js';

const canvas = document.getElementById('workstation-canvas');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xd0e8ff);
scene.fog = new THREE.FogExp2(0xd0e8ff, 0.025);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 2.4, 3.8);

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.target.set(0, 0.35, 0);
controls.maxDistance = 7;
controls.minDistance = 2;
controls.update();

const ambient = new THREE.AmbientLight(0xffffff, 0.8);
scene.add(ambient);

const keyLight = new THREE.DirectionalLight(0xffffff, 1.25);
keyLight.position.set(4, 6, 4);
keyLight.castShadow = true;
keyLight.shadow.mapSize.width = 1024;
keyLight.shadow.mapSize.height = 1024;
scene.add(keyLight);

const fillLight = new THREE.PointLight(0x66ccff, 0.7, 12);
fillLight.position.set(-3, 2, 3);
scene.add(fillLight);

const floorGeo = new THREE.CircleGeometry(1.35, 48);
const floorMat = new THREE.MeshStandardMaterial({
  color: 0x5ba848,
  roughness: 0.85,
  metalness: 0.0
});
const floor = new THREE.Mesh(floorGeo, floorMat);
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);

const ringGeo = new THREE.RingGeometry(1.32, 1.36, 48);
const ringMat = new THREE.MeshBasicMaterial({ color: 0xffaa00, side: THREE.DoubleSide });
const ring = new THREE.Mesh(ringGeo, ringMat);
ring.rotation.x = -Math.PI / 2;
ring.position.y = 0.01;
scene.add(ring);

let activeUnit = null;
let animations = [];
let activeType = 'worker';
const teamColor = new THREE.Color('#0077aa');

function hasActiveUnit(unitId) {
  return activeUnit?.userData.unitId === unitId;
}

function renderUnit(type) {
  if (activeUnit) {
    scene.remove(activeUnit);
  }

  activeType = type;
  animations = [];

  const unit = {
    id: `debug_${type}`,
    type,
    owner: 1,
    x: 0,
    z: 0
  };
  const unitObject = createUnitObject(unit, teamColor, hasActiveUnit);
  activeUnit = unitObject.group;
  activeUnit.userData.unitId = unit.id;
  activeUnit.position.set(0, 0.15, 0);
  animations = unitObject.animations;
  scene.add(activeUnit);

  document.querySelectorAll('.unit-button').forEach((button) => {
    button.classList.toggle('active', button.dataset.unitType === type);
  });
}

document.querySelectorAll('.unit-button').forEach((button) => {
  button.addEventListener('click', () => renderUnit(button.dataset.unitType));
});

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

function animate(timeMs) {
  const time = timeMs / 1000;
  requestAnimationFrame(animate);
  animations = animations.filter((animation) => !animation.update(time));
  if (activeUnit) {
    activeUnit.rotation.y += activeType === 'worker' ? 0.004 : 0.002;
  }
  controls.update();
  renderer.render(scene, camera);
}

renderUnit(activeType);
animate(0);
