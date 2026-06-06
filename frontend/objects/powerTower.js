import * as THREE from 'three';

export function createPowerTowerMesh(unit, teamColor, hasUnit) {
  const group = new THREE.Group();

  const baseMat = new THREE.MeshStandardMaterial({ color: 0x243447, roughness: 0.45, metalness: 0.65 });
  const neonMat = new THREE.MeshBasicMaterial({ color: teamColor });
  const coreMat = new THREE.MeshStandardMaterial({
    color: 0x66f6ff,
    emissive: 0x22d3ee,
    emissiveIntensity: 1.6,
    roughness: 0.2,
    metalness: 0.1
  });

  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.42, 0.16, 6), baseMat);
  base.position.y = 0.08;
  base.castShadow = true;
  base.receiveShadow = true;
  group.add(base);

  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.15, 0.72, 8), baseMat);
  mast.position.y = 0.48;
  mast.castShadow = true;
  group.add(mast);

  const ringGeo = new THREE.TorusGeometry(0.3, 0.025, 8, 28);
  ringGeo.rotateX(Math.PI / 2);
  const ring = new THREE.Mesh(ringGeo, neonMat);
  ring.position.y = 0.78;
  group.add(ring);

  const core = new THREE.Mesh(new THREE.OctahedronGeometry(0.18, 0), coreMat);
  core.position.y = 0.78;
  core.castShadow = true;
  group.add(core);

  const animation = {
    id: `tower_${unit.id}`,
    update: (time) => {
      if (!hasUnit(unit.id)) return true;
      ring.rotation.z = time * 0.9;
      core.rotation.y = time * 1.4;
      core.position.y = 0.78 + Math.sin(time * 3.2) * 0.035;
      return false;
    }
  };

  return { group, animations: [animation] };
}
