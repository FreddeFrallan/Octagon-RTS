// renderer.js
// 3D Scene and Visual Rendering using Three.js (Real-Time Hexagonal Edition)

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { getHexNeighbors, getHexDistance } from './game.js';
import { createBaseObject, createResourceObject, createUnitObject } from './objects/index.js';

export class GameRenderer {
  constructor(canvasId, game) {
    this.canvas = document.getElementById(canvasId);
    this.game = game;

    // Constants
    this.HEX_RADIUS = 1.0;
    this.HEX_WIDTH = Math.sqrt(3) * this.HEX_RADIUS; // ~1.732
    this.HEX_SPACING = 1.5 * this.HEX_RADIUS;
    
    const hasOddRows = this.game.gridHeight > 1;
    this.offsetX = ((this.game.gridWidth - 1 + (hasOddRows ? 0.5 : 0)) * this.HEX_WIDTH) / 2;
    this.offsetZ = ((this.game.gridHeight - 1) * this.HEX_SPACING) / 2;

    // Maps to track 3D objects
    this.tileMeshes = []; // 2D array [x][z]
    this.unitMeshes = new Map(); // unitId -> Group
    this.crystalMeshes = new Map(); // cellCoordString (e.g. "x,z") -> Group (gold resource nodes)
    this.baseMeshes = new Map(); // playerId -> Group
    this.fogMeshes = new Map(); // cellCoordString -> Mesh
    this.animations = []; // List of active animation objects
    this.lastFrameTimeMs = 0;
    this.isDisposed = false;
    this.animationFrameId = null;

    // Mouse interaction
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    this.initScene();
    this.createLights();
    this.createGrid();
    this.createSelectionRing();
    this.setupResizeHandler();

    // Event listeners
    this.setupGameEventListeners();

    // Start loop
    this.animate(0);
  }

  // Convert hexagonal offset coordinates to 3D world space
  gridToWorld(x, z) {
    const posX = (z % 2 === 0) ? (x * this.HEX_WIDTH) : ((x + 0.5) * this.HEX_WIDTH);
    const posZ = z * this.HEX_SPACING;
    return {
      x: posX - this.offsetX,
      y: 0.15, // top surface height
      z: posZ - this.offsetZ
    };
  }

  // Convert 3D world coordinates to grid coordinates
  worldToGrid(worldX, worldZ) {
    // Hex grids are easier to raycast, so we use direct intersection testing
    return null;
  }

  initScene() {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xd0e8ff); // Sky blue
    this.scene.fog = new THREE.FogExp2(0xd0e8ff, 0.012);

    this.camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
    this.camera.position.set(0, 16, 18);

    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true, alpha: false });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    this.controls.maxPolarAngle = Math.PI / 2.1;
    this.controls.minPolarAngle = Math.PI / 6;
    this.controls.minDistance = 5;
    this.controls.maxDistance = 45;
    this.controls.target.set(0, 0, 0);
  }

  createLights() {
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.1);
    this.scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xfffaf0, 1.6);
    dirLight.position.set(12, 22, 16);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 1024;
    dirLight.shadow.mapSize.height = 1024;
    dirLight.shadow.camera.near = 0.5;
    dirLight.shadow.camera.far = 50;
    const d = 15;
    dirLight.shadow.camera.left = -d;
    dirLight.shadow.camera.right = d;
    dirLight.shadow.camera.top = d;
    dirLight.shadow.camera.bottom = -d;
    dirLight.shadow.bias = -0.0005;
    this.scene.add(dirLight);

    const fillLight = new THREE.DirectionalLight(0xbadbff, 0.5);
    fillLight.position.set(-12, 6, -8);
    this.scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xfff5d0, 0.2);
    rimLight.position.set(0, -6, -12);
    this.scene.add(rimLight);
  }

  createGrid() {
    // Generate pointy-topped Hexagon shape
    const R = this.HEX_RADIUS;
    const shape = new THREE.Shape();
    shape.moveTo(0, R);
    for (let i = 1; i < 6; i++) {
      const angle = (i * Math.PI) / 3;
      shape.lineTo(R * Math.sin(angle), R * Math.cos(angle));
    }
    shape.closePath();

    const extrudeSettings = {
      depth: 0.3,
      bevelEnabled: true,
      bevelSegments: 2,
      steps: 1,
      bevelSize: 0.04,
      bevelThickness: 0.04
    };

    const hexGeometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);
    hexGeometry.rotateX(-Math.PI / 2);
    hexGeometry.center();

    // Grassy green tile material
    const defaultTileMaterial = new THREE.MeshStandardMaterial({
      color: 0x5ba848,
      emissive: 0x0a2205,
      roughness: 0.85,
      metalness: 0.0
    });

    const borderMaterial = new THREE.LineBasicMaterial({
      color: 0x327325, // dark outline
      linewidth: 2
    });

    const edgesGeometry = new THREE.EdgesGeometry(hexGeometry);

    for (let x = 0; x < this.game.gridWidth; x++) {
      this.tileMeshes[x] = [];
      for (let z = 0; z < this.game.gridHeight; z++) {
        const cell = this.game.grid[x][z];
        const pos = this.gridToWorld(x, z);

        if (cell.type === 'obstacle') {
          this.tileMeshes[x][z] = null;
          continue;
        }

        const tileGroup = new THREE.Group();
        tileGroup.position.set(pos.x, 0, pos.z);

        // Render hexes at 96% scale to allow water paths to show through!
        const mesh = new THREE.Mesh(hexGeometry, defaultTileMaterial.clone());
        mesh.scale.set(0.96, 1.0, 0.96);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh.userData = { x, z, isOctagon: true }; // keeps parameter compat
        tileGroup.add(mesh);

        const outline = new THREE.LineSegments(edgesGeometry, borderMaterial.clone());
        outline.scale.set(0.96, 1.0, 0.96);
        outline.position.y = 0.001; 
        tileGroup.add(outline);

        const fogGeometry = new THREE.CircleGeometry(this.HEX_RADIUS * 0.96, 6);
        fogGeometry.rotateX(-Math.PI / 2);
        const fogMaterial = new THREE.MeshBasicMaterial({
          color: 0x1f2937,
          transparent: true,
          opacity: 0.62,
          side: THREE.DoubleSide,
          depthWrite: false
        });
        const fogMesh = new THREE.Mesh(fogGeometry, fogMaterial);
        fogMesh.rotation.y = Math.PI / 6;
        fogMesh.position.y = 0.22;
        fogMesh.visible = cell.visible === false;
        tileGroup.add(fogMesh);
        this.fogMeshes.set(`${x},${z}`, fogMesh);

        this.scene.add(tileGroup);
        this.tileMeshes[x][z] = tileGroup;

        if (cell.type === 'base') {
          this.createBaseMesh(x, z, cell.owner);
        } else if (cell.type === 'resource') {
          this.createCrystalMesh(x, z, cell.gold);
        }
      }
    }

    // Flat ground water mesh (below hexes)
    const waterGeo = new THREE.PlaneGeometry(30, 30);
    const waterMat = new THREE.MeshStandardMaterial({
      color: 0x4499dd,
      roughness: 0.2,
      metalness: 0.1,
      emissive: 0x051e3b,
      emissiveIntensity: 0.8
    });
    const water = new THREE.Mesh(waterGeo, waterMat);
    water.rotateX(-Math.PI / 2);
    water.position.y = -0.05;
    water.receiveShadow = true;
    this.scene.add(water);
  }

  createSelectionRing() {
    // Hexagonal ring highlight
    const ringGeo = new THREE.RingGeometry(this.HEX_RADIUS * 0.85, this.HEX_RADIUS * 0.95, 6);
    ringGeo.rotateX(-Math.PI / 2);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0xffaa00,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0
    });
    this.selectionRing = new THREE.Mesh(ringGeo, ringMat);
    this.selectionRing.position.set(0, 0.16, 0);
    this.scene.add(this.selectionRing);

    this.animations.push({
      update: (time) => {
        if (this.selectionRing.visible) {
          this.selectionRing.rotation.y = time * 0.5;
          ringMat.opacity = 0.7 + 0.3 * Math.sin(time * 4);
        }
      }
    });
  }

  createBaseMesh(x, z, ownerId) {
    if (this.baseMeshes.has(ownerId)) return;

    const pos = this.gridToWorld(x, z);
    const player = this.game.players[ownerId];
    const color = new THREE.Color(player.color);
    const baseObject = createBaseObject(color);
    const group = baseObject.group;
    group.position.set(pos.x, pos.y, pos.z);
    this.scene.add(group);

    this.baseMeshes.set(ownerId, group);
    baseObject.animations.forEach(animation => {
      animation.id = `base_${ownerId}`;
    });
    this.animations.push(...baseObject.animations);

    this.setTileOutlineColor(x, z, color);
  }

  createCrystalMesh(x, z, goldAmount) {
    const coordStr = `${x},${z}`;
    if (this.crystalMeshes.has(coordStr)) return;

    const pos = this.gridToWorld(x, z);
    const resourceObject = createResourceObject(x, z);
    const group = resourceObject.group;
    group.position.set(pos.x, pos.y, pos.z);

    this.scene.add(group);
    this.crystalMeshes.set(coordStr, group);
    resourceObject.animations.forEach(animation => {
      animation.id = `resource_${coordStr}`;
    });
    this.animations.push(...resourceObject.animations);

    this.setTileOutlineColor(x, z, new THREE.Color(0xffaa00));
  }

  createUnitMesh(unit) {
    const player = this.game.players[unit.owner];
    const teamColor = new THREE.Color(player ? player.color : 0xcccccc);
    const unitObject = createUnitObject(unit, teamColor, (unitId) => this.unitMeshes.has(unitId));
    const group = unitObject.group;
    const pos = this.gridToWorld(unit.x, unit.z);
    
    const offset = this.getStackOffset(unit.id, unit.x, unit.z);
    group.position.set(pos.x + offset.x, pos.y, pos.z + offset.z);

    this.animations.push(...unitObject.animations);

    this.scene.add(group);
    this.unitMeshes.set(unit.id, group);
    return group;
  }

  // --- Grid and Outline Helpers ---

  setTileOutlineColor(x, z, color) {
    const tileGroup = this.tileMeshes[x][z];
    if (tileGroup) {
      const outline = tileGroup.children.find(c => c instanceof THREE.LineSegments);
      if (outline) {
        outline.material.color.copy(color);
        outline.material.transparent = true;
        outline.material.opacity = 0.8;
      }
    }
  }

  resetTileOutlineColor(x, z) {
    const cell = this.game.grid[x][z];
    let color = new THREE.Color(0x327325); // default grass border

    if (cell.type === 'base') {
      color.copy(new THREE.Color(this.game.players[cell.owner].color));
    } else if (cell.type === 'resource') {
      color.copy(new THREE.Color(0xffaa00));
    } else if (cell.type === 'obstacle') {
      color.copy(new THREE.Color(0x4499dd));
    }

    this.setTileOutlineColor(x, z, color);
  }

  // Highlight 6 hexagonal adjacent tiles in Green.
  highlightMovementTiles(centerX, centerZ, enable, selectedUnits = []) {
    const neighbors = getHexNeighbors(centerX, centerZ, this.game.gridWidth, this.game.gridHeight);
    for (const n of neighbors) {
      const cell = this.game.getCell(n.x, n.z);
      const canEnter = cell && cell.type !== 'base' && cell.type !== 'obstacle' && cell.type !== 'resource';
      if (canEnter) {
        if (enable) {
          this.setTileOutlineColor(n.x, n.z, new THREE.Color(0x39ff14));
        } else {
          const isSelected = this.game.selectedCell && this.game.selectedCell.x === n.x && this.game.selectedCell.z === n.z;
          if (isSelected) {
            this.setTileOutlineColor(n.x, n.z, new THREE.Color(0xffaa00));
          } else {
            this.resetTileOutlineColor(n.x, n.z);
          }
        }
      } else if (!enable && cell) {
        this.resetTileOutlineColor(n.x, n.z);
      }
    }
  }

  // Highlight all tiles in range in Red
  highlightAttackTiles(centerX, centerZ, enable) {
    const artConfig = (window.UNITS_CONFIG && window.UNITS_CONFIG.artillery) || { minRange: 1, maxRange: 2 };
    const minRange = artConfig.minRange ?? 1;
    const maxRange = artConfig.maxRange ?? 2;
    for (let tx = 0; tx < this.game.gridWidth; tx++) {
      for (let tz = 0; tz < this.game.gridHeight; tz++) {
        const dist = getHexDistance(centerX, centerZ, tx, tz);
        if (dist >= minRange && dist <= maxRange) {
          if (enable) {
            this.setTileOutlineColor(tx, tz, new THREE.Color(0xff0000));
          } else {
            const isSelected = this.game.selectedCell && this.game.selectedCell.x === tx && this.game.selectedCell.z === tz;
            if (isSelected) {
              this.setTileOutlineColor(tx, tz, new THREE.Color(0xffaa00));
            } else {
              this.resetTileOutlineColor(tx, tz);
            }
          }
        }
      }
    }
  }


  getStackOffset(unitId, x, z) {
    const cell = this.game.grid[x][z];
    if (!cell) return { x: 0, z: 0 };
    
    const units = [...cell.units].sort((a, b) => a.id.localeCompare(b.id));
    const idx = units.findIndex(u => u.id === unitId);

    if (idx === -1 || units.length <= 1) return { x: 0, z: 0 };

    const angle = (idx / units.length) * Math.PI * 2;
    const r = 0.35;
    return {
      x: Math.cos(angle) * r,
      z: Math.sin(angle) * r
    };
  }

  // --- Interactive updates ---

  updateSelection(selectedCell) {
    const ringMat = this.selectionRing.material;
    
    if (selectedCell) {
      const pos = this.gridToWorld(selectedCell.x, selectedCell.z);
      this.selectionRing.position.set(pos.x, pos.y + 0.02, pos.z);
      this.selectionRing.visible = true;
      ringMat.opacity = 0.8;
      
      this.setTileOutlineColor(selectedCell.x, selectedCell.z, new THREE.Color(0xffaa00));
    } else {
      this.selectionRing.visible = false;
      ringMat.opacity = 0;
    }

    // Reset other tiles outlines
    for (let x = 0; x < this.game.gridWidth; x++) {
      for (let z = 0; z < this.game.gridHeight; z++) {
        if (!selectedCell || selectedCell.x !== x || selectedCell.z !== z) {
          this.resetTileOutlineColor(x, z);
        }
      }
    }
  }

  // Real-time synchronization
  syncScene() {
    const currentUnitIds = new Set();

    for (let x = 0; x < this.game.gridWidth; x++) {
      for (let z = 0; z < this.game.gridHeight; z++) {
        const cell = this.game.grid[x][z];
        const fogMesh = this.fogMeshes.get(`${x},${z}`);
        if (fogMesh) {
          fogMesh.visible = cell.visible === false;
        }

        cell.units.forEach(unit => {
          currentUnitIds.add(unit.id);
          let meshGroup = this.unitMeshes.get(unit.id);

          if (!meshGroup) {
            meshGroup = this.createUnitMesh(unit);
          }

          const offsetCellX = unit.isMoving && unit.targetX !== null && unit.targetX !== undefined ? unit.targetX : unit.x;
          const offsetCellZ = unit.isMoving && unit.targetZ !== null && unit.targetZ !== undefined ? unit.targetZ : unit.z;
          const offset = this.getStackOffset(unit.id, offsetCellX, offsetCellZ);
          
          meshGroup.userData.renderState = {
            x: unit.x,
            z: unit.z,
            isMoving: unit.isMoving,
            targetX: unit.targetX,
            targetZ: unit.targetZ,
            moveStartX: unit.moveStartX,
            moveStartZ: unit.moveStartZ,
            moveStartTime: unit.moveStartTime,
            moveEndTime: unit.moveEndTime,
            offsetX: offset.x,
            offsetZ: offset.z
          };
        });
      }
    }

    // Clean up mechs that died
    this.unitMeshes.forEach((mesh, id) => {
      if (!currentUnitIds.has(id)) {
        this.createExplosion(mesh.position.x, mesh.position.y + 0.3, mesh.position.z);
        this.scene.remove(mesh);
        this.animations = this.animations.filter(anim => anim.id !== `bob_${id}`);
        this.unitMeshes.delete(id);
      }
    });

    // Sync Gold Nuggets Scaling
    for (let x = 0; x < this.game.gridWidth; x++) {
      for (let z = 0; z < this.game.gridHeight; z++) {
        const cell = this.game.grid[x][z];
        const coordStr = `${x},${z}`;
        
        if (cell.type === 'resource' && cell.gold > 0) {
          if (!this.crystalMeshes.has(coordStr)) {
            this.createCrystalMesh(x, z, cell.gold);
          }
          
          const group = this.crystalMeshes.get(coordStr);
          group.visible = cell.visible !== false;
          const scaleRatio = cell.gold / cell.maxGold;
          // Scale all nuggets down smoothly
          group.scale.set(scaleRatio, scaleRatio, scaleRatio);
        } else {
          if (this.crystalMeshes.has(coordStr)) {
            const group = this.crystalMeshes.get(coordStr);
            this.scene.remove(group);
            this.animations = this.animations.filter(anim => anim.id !== `resource_${coordStr}`);
            this.crystalMeshes.delete(coordStr);
            this.resetTileOutlineColor(x, z);
          }
        }
      }
    }
  }

  getUnitDesiredPosition(renderState) {
    if (renderState.isMoving && renderState.targetX !== null && renderState.targetX !== undefined && renderState.targetZ !== null && renderState.targetZ !== undefined) {
      const serverNow = Date.now();
      const duration = renderState.moveEndTime - renderState.moveStartTime;
      const elapsed = serverNow - renderState.moveStartTime;
      const t = Math.max(0, Math.min(elapsed / (duration || 1), 1.0));
      const ease = t * (2 - t);

      const startX = renderState.moveStartX !== null && renderState.moveStartX !== undefined ? renderState.moveStartX : renderState.x;
      const startZ = renderState.moveStartZ !== null && renderState.moveStartZ !== undefined ? renderState.moveStartZ : renderState.z;
      const startWorld = this.gridToWorld(startX, startZ);
      const targetWorld = this.gridToWorld(renderState.targetX, renderState.targetZ);

      return new THREE.Vector3(
        startWorld.x + (targetWorld.x - startWorld.x) * ease + renderState.offsetX,
        0.15 + Math.sin(t * Math.PI) * 0.4,
        startWorld.z + (targetWorld.z - startWorld.z) * ease + renderState.offsetZ
      );
    }

    const pos = this.gridToWorld(renderState.x, renderState.z);
    return new THREE.Vector3(pos.x + renderState.offsetX, 0.15, pos.z + renderState.offsetZ);
  }

  updateUnitVisuals(deltaSeconds) {
    const smoothing = 1 - Math.exp(-deltaSeconds * 18);

    this.unitMeshes.forEach(meshGroup => {
      const renderState = meshGroup.userData.renderState;
      if (!renderState) return;

      meshGroup.position.lerp(this.getUnitDesiredPosition(renderState), smoothing);
    });
  }

  // --- Effects and Explosions ---

  createExplosion(x, y, z, duration = 500) {
    if (typeof duration !== 'number' || isNaN(duration)) {
      duration = 500;
    }
    const particleCount = 12;
    const geometry = new THREE.SphereGeometry(0.06, 4, 4);
    const material = new THREE.MeshBasicMaterial({ color: 0xff8800, transparent: true, opacity: 0.9 });
    const particles = [];
    const velocities = [];

    for (let i = 0; i < particleCount; i++) {
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(x, y, z);
      this.scene.add(mesh);
      particles.push(mesh);

      const theta = Math.random() * Math.PI * 2;
      const phi = Math.random() * Math.PI;
      const speed = 0.04 + Math.random() * 0.06;

      velocities.push(new THREE.Vector3(
        Math.sin(phi) * Math.cos(theta) * speed,
        (Math.sin(phi) * Math.sin(theta) * speed) + 0.02,
        Math.cos(phi) * speed
      ));
    }

    const startTime = performance.now();

    const particleAnim = {
      update: () => {
        const elapsed = performance.now() - startTime;
        const t = Math.min(elapsed / duration, 1.0);

        if (t >= 1.0) {
          particles.forEach(p => this.scene.remove(p));
          geometry.dispose();
          material.dispose();
          return true;
        }

        material.opacity = 0.9 * (1 - t);

        particles.forEach((p, i) => {
          const vel = velocities[i];
          p.position.add(vel);
          vel.y -= 0.001 * (500 / duration);
          p.scale.setScalar(Math.max(0.001, 1 - t));
        });

        return false;
      }
    };

    this.animations.push(particleAnim);
  }

  createLaserBeam(fromPos, toPos, colorHex = 0xff0055) {
    const distance = fromPos.distanceTo(toPos);
    const geometry = new THREE.CylinderGeometry(0.03, 0.03, distance, 6);
    geometry.rotateX(Math.PI / 2);
    geometry.translate(0, 0, distance / 2);

    const material = new THREE.MeshBasicMaterial({ color: colorHex, transparent: true, opacity: 0.85 });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(fromPos);
    mesh.lookAt(toPos);
    this.scene.add(mesh);

    const startTime = performance.now();
    const duration = 250;

    const laserAnim = {
      update: () => {
        const elapsed = performance.now() - startTime;
        const t = elapsed / duration;

        if (t >= 1.0) {
          this.scene.remove(mesh);
          geometry.dispose();
          material.dispose();
          return true;
        }

        mesh.scale.set(1 - t, 1 - t, 1);
        material.opacity = 0.85 * (1 - t);
        return false;
      }
    };
    this.animations.push(laserAnim);
  }

  // Parabolic Plasma Shell Arc Firing FX
  createArtilleryShellArc(fromX, fromZ, toX, toZ, flightTime = 1000) {
    const start = this.gridToWorld(fromX, fromZ);
    const end = this.gridToWorld(toX, toZ);
    
    const startPos = new THREE.Vector3(start.x, start.y + 0.35, start.z);
    const endPos = new THREE.Vector3(end.x, end.y + 0.1, end.z);
    
    const projectileGeo = new THREE.SphereGeometry(0.15, 8, 8);
    const projectileMat = new THREE.MeshBasicMaterial({
      color: 0xffaa00, // Golden blast plasma
      transparent: true,
      opacity: 0.95
    });
    const projectile = new THREE.Mesh(projectileGeo, projectileMat);
    this.scene.add(projectile);

    const startTime = performance.now();
    const duration = typeof flightTime === 'number' && !isNaN(flightTime) && flightTime > 0 ? flightTime : 1000;

    const arcAnim = {
      update: () => {
        const elapsed = performance.now() - startTime;
        const t = Math.min(elapsed / duration, 1.0);
        
        const currentX = startPos.x + (endPos.x - startPos.x) * t;
        const currentZ = startPos.z + (endPos.z - startPos.z) * t;
        
        // Parabolic height curve
        const peakHeight = 3.5;
        const currentY = startPos.y + (endPos.y - startPos.y) * t + Math.sin(t * Math.PI) * peakHeight;
        
        projectile.position.set(currentX, currentY, currentZ);
        
        // Read traceFadeTime dynamically from Artillery animation configuration
        const artConfig = (window.UNITS_CONFIG && window.UNITS_CONFIG.artillery) || {};
        const animConfig = artConfig.animation || {};
        let traceDuration = animConfig.traceFadeTime ?? 1000;
        if (typeof traceDuration !== 'number' || isNaN(traceDuration)) {
          traceDuration = 1000;
        }

        // Spawn small tail spark trail
        if (Math.random() < 0.35) {
          this.createExplosion(currentX, currentY, currentZ, traceDuration);
        }

        if (t >= 1.0) {
          this.scene.remove(projectile);
          projectileGeo.dispose();
          projectileMat.dispose();
          
          // Triple cluster blast on impact
          this.createExplosion(endPos.x, endPos.y + 0.2, endPos.z, traceDuration);
          setTimeout(() => {
            this.createExplosion(endPos.x + 0.25, endPos.y + 0.15, endPos.z - 0.15, traceDuration);
            this.createExplosion(endPos.x - 0.25, endPos.y + 0.15, endPos.z + 0.15, traceDuration);
          }, 80);
          return true;
        }
        return false;
      }
    };
    this.animations.push(arcAnim);
  }

  setupGameEventListeners() {
    // Handled in app.js
  }

  showFloatingDamageText(gridX, gridZ, text, colorCSS) {
    const worldPos = this.gridToWorld(gridX, gridZ);
    worldPos.y += 0.8;

    const el = document.createElement('div');
    el.innerText = text;
    el.style.position = 'absolute';
    el.style.color = colorCSS;
    el.style.fontFamily = 'Orbitron, sans-serif';
    el.style.fontWeight = 'bold';
    el.style.fontSize = '1.1rem';
    el.style.pointerEvents = 'none';
    el.style.textShadow = '0 0 5px rgba(255, 255, 255, 0.8), 0 0 10px';
    el.style.zIndex = '50';
    el.style.transform = 'translate(-50%, -50%)';
    el.style.transition = 'all 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
    document.getElementById('game-container').appendChild(el);

    const project = () => {
      const tempV = new THREE.Vector3(worldPos.x, worldPos.y, worldPos.z);
      tempV.project(this.camera);
      const x = (tempV.x *  .5 + .5) * window.innerWidth;
      const y = (tempV.y * -.5 + .5) * window.innerHeight;
      el.style.left = `${x}px`;
      el.style.top = `${y}px`;
    };

    project();

    requestAnimationFrame(() => {
      worldPos.y += 1.2;
      el.style.opacity = '0';
      el.style.transform = 'translate(-50%, -100%) scale(1.3)';
    });

    const updateInterval = setInterval(() => {
      project();
    }, 16);

    setTimeout(() => {
      clearInterval(updateInterval);
      el.remove();
    }, 850);
  }

  animate(timeMs) {
    if (this.isDisposed) return;
    this.animationFrameId = requestAnimationFrame((t) => this.animate(t));
    this.controls.update();

    const deltaSeconds = this.lastFrameTimeMs > 0 ? Math.min((timeMs - this.lastFrameTimeMs) / 1000, 0.1) : 0;
    this.lastFrameTimeMs = timeMs;

    const time = timeMs / 1000;
    this.updateUnitVisuals(deltaSeconds);

    const activeAnimations = this.animations;
    this.animations = [];
    activeAnimations.forEach(anim => {
      if (!anim.update(time)) {
        this.animations.push(anim);
      }
    });

    this.renderer.render(this.scene, this.camera);
  }

  setupResizeHandler() {
    this.handleResize = () => {
      this.camera.aspect = window.innerWidth / window.innerHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(window.innerWidth, window.innerHeight);
    };
    window.addEventListener('resize', this.handleResize);
  }

  dispose() {
    this.isDisposed = true;
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
    if (this.handleResize) {
      window.removeEventListener('resize', this.handleResize);
    }
    this.animations = [];
    this.unitMeshes.clear();
    this.crystalMeshes.clear();
    this.baseMeshes.clear();
    this.fogMeshes.clear();
    if (this.controls) {
      this.controls.dispose();
    }
    if (this.renderer) {
      this.renderer.dispose();
    }
  }

  raycastTile(clientX, clientY) {
    this.mouse.x = (clientX / window.innerWidth) * 2 - 1;
    this.mouse.y = -(clientY / window.innerHeight) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);

    const meshesToTest = [];
    for (let x = 0; x < this.game.gridWidth; x++) {
      for (let z = 0; z < this.game.gridHeight; z++) {
        const tileGroup = this.tileMeshes[x][z];
        if (tileGroup && tileGroup.children[0]) {
          meshesToTest.push(tileGroup.children[0]);
        }
      }
    }

    const intersects = this.raycaster.intersectObjects(meshesToTest);
    if (intersects.length > 0) {
      return intersects[0].object.userData;
    }
    return null;
  }
}
