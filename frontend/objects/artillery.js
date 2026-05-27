import * as THREE from 'three';

export function createArtilleryMesh(unit, teamColor, hasUnit) {
  // --- CONFIGURABLE VARIABLES ---
  const config = {
    furnaceRadius: 0.18,
    furnaceDepth: 0.05,
    lavaBaseColor: 0xff3300,
    lavaGlowColor: 0xffaa00,
  };
  // ------------------------------

  const group = new THREE.Group();

  // Materials
  const darkMetalMat = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.4, metalness: 0.6 });
  const neonMat = new THREE.MeshBasicMaterial({ color: teamColor });

  // Base Shared Lava Material
  const baseLavaMat = new THREE.MeshStandardMaterial({
    color: config.lavaBaseColor,
    emissive: config.lavaBaseColor,
    emissiveIntensity: 1.5,
    roughness: 0.2,
    metalness: 0.1
  });

  // 1. Perfect Square Platform
  const platformGeo = new THREE.BoxGeometry(0.65, 0.15, 0.65);
  const platform = new THREE.Mesh(platformGeo, darkMetalMat);
  platform.position.y = 0.075;
  platform.castShadow = true;
  platform.receiveShadow = true;
  group.add(platform);

  // 2. Square House / Furnace Outer Walls
  const houseGeo = new THREE.BoxGeometry(0.45, 0.25, 0.45);
  const house = new THREE.Mesh(houseGeo, darkMetalMat);
  house.position.y = 0.275;
  house.castShadow = true;
  group.add(house);

  // 3. Perfect Circle Furnace Pool
  const furnaceGroup = new THREE.Group();
  furnaceGroup.position.y = 0.4;

  // Inner Lava Pool (CLONED so it has its own independent animation instance)
  const lavaGeo = new THREE.CylinderGeometry(config.furnaceRadius, config.furnaceRadius, 0.01, 24);
  const uniqueLavaMat = baseLavaMat.clone(); // <--- FIX: Clones the material for this specific mesh
  const lava = new THREE.Mesh(lavaGeo, uniqueLavaMat);
  lava.position.y = 0.006;
  furnaceGroup.add(lava);

  // Dark rim/lip to frame the circle furnace pool
  const rimMat = new THREE.MeshStandardMaterial({ color: 0x222a36, roughness: 0.6, metalness: 0.8 });
  const rimGeo = new THREE.TorusGeometry(config.furnaceRadius + 0.015, 0.018, 8, 24);
  rimGeo.rotateX(Math.PI / 2);
  const rim = new THREE.Mesh(rimGeo, rimMat);
  rim.position.y = 0.018;
  furnaceGroup.add(rim);

  group.add(furnaceGroup);

  // 4. Square Decorative Player Stripe Band
  const stripGeo = new THREE.BoxGeometry(0.69, 0.04, 0.69);
  const strip = new THREE.Mesh(stripGeo, neonMat);
  strip.position.y = 0.075;
  group.add(strip);

  // 5. Animation (Lava fire pulsing + subtle mechanical idle rotation)
  const colorBase = new THREE.Color(config.lavaBaseColor);
  const colorGlow = new THREE.Color(config.lavaGlowColor);

  const animation = {
    id: `bob_${unit.id}`,
    update: (time) => {
      if (!hasUnit(unit.id)) return true;

      // Idle house rotation
      house.rotation.y = Math.sin(time * 0.5) * 0.1;
      furnaceGroup.rotation.y = house.rotation.y;

      // Churning fire math wave
      const pulseFactor = (Math.sin(time * 4.5) + 1.0) / 2.0;

      // Update the UNIQUE material instance explicitly assigned to this lava mesh
      lava.material.color.copy(colorBase).lerp(colorGlow, pulseFactor * 0.5);
      lava.material.emissive.copy(colorBase).lerp(colorGlow, pulseFactor);
      lava.material.emissiveIntensity = 1.2 + pulseFactor * 1.3; // Cranked up intensity variance for higher visibility

      return false;
    }
  };

  return { group, animations: [animation] };
}
