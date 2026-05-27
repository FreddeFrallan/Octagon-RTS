import * as THREE from 'three';

export function createMechMesh(unit, teamColor, hasUnit) {
  // --- CONFIGURABLE VARIABLES ---
  const config = {
    spikeLength: 0.55,       // Length of the spinning spikes
    spikeWidth: 0.04,        // Thickness of the base of the spike
    spikeCount: 12,          // Total number of spikes in the ring
    spikeRadius: 0.26,       // Distance of the spikes from the center core
    treadNeonHeight: 0.12,   // TALLER STRIPE: Increased from 0.04 for a bolder team color look
  };
  // ------------------------------

  const group = new THREE.Group();

  // Materials
  const darkMetalMat = new THREE.MeshStandardMaterial({ color: 0x445566, roughness: 0.4, metalness: 0.8 });
  const spikeMat = new THREE.MeshStandardMaterial({ color: 0xcca625, roughness: 0.3, metalness: 0.7 }); // Metallic bronze/brass
  const neonMat = new THREE.MeshBasicMaterial({ color: teamColor });

  // 1. Circular Tank Chassis/Hull
  const chassisGeo = new THREE.CylinderGeometry(0.38, 0.38, 0.25, 32);
  const chassis = new THREE.Mesh(chassisGeo, darkMetalMat);
  chassis.position.y = 0.125;
  chassis.castShadow = true;
  chassis.receiveShadow = true;
  group.add(chassis);

  // 2. Decorative Neon Side Ring (Uses the new config height)
  const treadNeonGeo = new THREE.CylinderGeometry(0.4, 0.4, config.treadNeonHeight, 32, 1, true);
  const treadNeon = new THREE.Mesh(treadNeonGeo, neonMat);
  treadNeon.position.y = 0.125; // Centered vertically with the chassis
  group.add(treadNeon);

  // 3. Circular Spike Platform
  const platformGeo = new THREE.CylinderGeometry(0.25, 0.28, 0.06, 32);
  const platform = new THREE.Mesh(platformGeo, darkMetalMat);
  platform.position.y = 0.28;
  platform.castShadow = true;
  group.add(platform);

  // 4. Ring of Horizontal Spikes (Buzz-saw style)
  const spikeGroup = new THREE.Group();
  spikeGroup.position.y = 0.28;

  const spikeGeo = new THREE.ConeGeometry(config.spikeWidth, config.spikeLength, 4);
  spikeGeo.rotateX(Math.PI / 2);

  for (let i = 0; i < config.spikeCount; i++) {
    const angle = (i / config.spikeCount) * Math.PI * 2;
    const spike = new THREE.Mesh(spikeGeo, spikeMat);

    spike.position.x = Math.cos(angle) * config.spikeRadius;
    spike.position.z = Math.sin(angle) * config.spikeRadius;

    spike.rotation.y = -angle + Math.PI / 2;
    spike.castShadow = true;

    spikeGroup.add(spike);
  }
  group.add(spikeGroup);

  // 5. Animation (The spike ring rotates menacingly)
  const randomPhase = Math.random() * Math.PI * 2;
  const animation = {
    id: `bob_${unit.id}`,
    update: (time) => {
      if (!hasUnit(unit.id)) return true;

      // Constant spinning animation for the horizontal spike wheel
      spikeGroup.rotation.y = time * 0.5 + randomPhase;

      // Subtle tank hull engine vibration
      chassis.position.y = 0.125 + Math.sin(time * 8.0) * 0.005;
      treadNeon.position.y = chassis.position.y;

      return false;
    }
  };

  return { group, animations: [animation] };
}