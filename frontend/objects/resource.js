import * as THREE from 'three';

// Added clusterScale parameter (default to 1.0 if not provided)
export function createResourceObject(x = 0, z = 0, pulseSpeed = 2.5, clusterScale = 2.0) {
  const group = new THREE.Group();

  // --- CONFIGURABLE VARIABLES ---
  const minRocks = 6;
  const maxRocks = 11;
  const numNuggets = Math.floor(Math.random() * (maxRocks - minRocks + 1)) + minRocks;

  // Color Definitions
  const COLOR_BASE_GOLD = 0xffd700;
  const COLOR_SHIMMER_GOLD = 0xfffae6;

  // Shared base material template
  const baseGoldMat = new THREE.MeshStandardMaterial({
    color: COLOR_BASE_GOLD,
    roughness: 0.18,
    metalness: 0.95,
    emissive: COLOR_SHIMMER_GOLD,
    emissiveIntensity: 0.1
  });

  const rockMat = new THREE.MeshStandardMaterial({
    color: 0x3a3330,
    roughness: 0.95,
    metalness: 0.0
  });

  // Array to track meshes that need individual color updates
  const animatedSpikes = [];

  // 1. Shattered Bedrock Base (Always flat)
  const baseCount = 3;
  const baseGeo = new THREE.DodecahedronGeometry(0.2, 0);
  for (let b = 0; b < baseCount; b++) {
    const baseMesh = new THREE.Mesh(baseGeo, rockMat);
    baseMesh.position.set(
      (Math.random() - 0.5) * 0.25,
      0.01,
      (Math.random() - 0.5) * 0.25
    );
    baseMesh.scale.set(1.6 + Math.random() * 0.8, 0.15 + Math.random() * 0.1, 1.6 + Math.random() * 0.8);
    baseMesh.rotation.set(0, Math.random() * Math.PI, 0);

    baseMesh.castShadow = true;
    baseMesh.receiveShadow = true;
    group.add(baseMesh);
  }

  // 2. Sharp, Errupting Gold Crystal Spikes
  const spikeGeo = new THREE.ConeGeometry(0.09, 0.6, 4);
  spikeGeo.translate(0, 0.3, 0);

  for (let i = 0; i < numNuggets; i++) {
    const uniqueSpikeMat = baseGoldMat.clone();
    const mesh = new THREE.Mesh(spikeGeo, uniqueSpikeMat);

    const angle = (i / numNuggets) * Math.PI * 2 + (Math.random() * 0.6 - 0.3);
    const radius = Math.random() * 0.24;

    const cx = Math.cos(angle) * radius;
    const cz = Math.sin(angle) * radius;
    mesh.position.set(cx, -0.02, cz);

    // Sizing logic
    const sizeRoll = Math.random();
    let scaleX, scaleY, scaleZ;

    if (sizeRoll > 0.75) {
      scaleY = 1.4 + Math.random() * 0.9;
      scaleX = scaleZ = 1.0 + Math.random() * 0.4;
    } else if (sizeRoll > 0.3) {
      scaleY = 0.7 + Math.random() * 0.5;
      scaleX = scaleZ = 0.6 + Math.random() * 0.3;
    } else {
      scaleY = 0.2 + Math.random() * 0.3;
      scaleX = scaleZ = 0.3 + Math.random() * 0.2;
    }
    mesh.scale.set(scaleX, scaleY, scaleZ);

    mesh.rotation.y = Math.random() * Math.PI * 2;

    const radialTilt = 0.05 + (radius * 1.3);
    const randomTiltX = (Math.random() - 0.5) * 0.4;
    const randomTiltZ = (Math.random() - 0.5) * 0.4;

    mesh.rotation.x = radialTilt + randomTiltX;
    mesh.rotation.z = randomTiltZ;

    mesh.castShadow = true;
    mesh.receiveShadow = true;

    animatedSpikes.push({
      mesh: mesh,
      speedModifier: 0.8 + Math.random() * 0.6,
      phaseOffset: Math.random() * Math.PI * 2
    });

    group.add(mesh);
  }

  // Position the cluster on global grid coordinates
  group.position.set(x, 0, z);

  // GLOBAL SCALE FACTOR: Scale the entire unified parent group container instantly
  group.scale.set(clusterScale, clusterScale, clusterScale);

  // Targets for interpolation
  const goldColorTarget = new THREE.Color(COLOR_BASE_GOLD);
  const shimmerColorTarget = new THREE.Color(COLOR_SHIMMER_GOLD);

  return {
    group,
    animations: [{
      update: (time) => {
        for (let s = 0; s < animatedSpikes.length; s++) {
          const item = animatedSpikes[s];
          const mat = item.mesh.material;

          const individualTime = time * pulseSpeed * item.speedModifier + item.phaseOffset;
          const pulseFactor = (Math.sin(individualTime) + 1.0) / 2.0;

          mat.color.copy(goldColorTarget).lerp(shimmerColorTarget, pulseFactor * 0.3);
          mat.emissive.copy(shimmerColorTarget);
          mat.emissiveIntensity = 0.05 + pulseFactor * 0.55;
        }

        return false;
      }
    }]
  };
}