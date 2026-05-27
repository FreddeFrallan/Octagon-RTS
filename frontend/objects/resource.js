import * as THREE from 'three';

export function createResourceObject(x = 0, z = 0) {
  const group = new THREE.Group();
  const numNuggets = 4;
  const goldGeo = new THREE.DodecahedronGeometry(0.16);
  const goldMat = new THREE.MeshStandardMaterial({
    color: 0xffaa00,
    roughness: 0.1,
    metalness: 0.9,
    emissive: 0x553300,
    emissiveIntensity: 0.4
  });

  for (let i = 0; i < numNuggets; i++) {
    const mesh = new THREE.Mesh(goldGeo, goldMat);
    const angle = (i / numNuggets) * Math.PI * 2 + Math.random() * 0.5;
    const radius = 0.25 + Math.random() * 0.12;
    const cx = Math.cos(angle) * radius;
    const cz = Math.sin(angle) * radius;

    mesh.position.set(cx, 0.16, cz);
    mesh.scale.set(1 + Math.random() * 0.4, 0.7 + Math.random() * 0.5, 1 + Math.random() * 0.4);
    mesh.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, Math.random() * Math.PI);
    mesh.castShadow = true;
    group.add(mesh);
  }

  return {
    group,
    animations: [{
      update: (time) => {
        goldMat.emissiveIntensity = 0.3 + 0.2 * Math.sin(time * 3 + (x + z) * 0.5);
        return false;
      }
    }]
  };
}
