import * as THREE from 'three';

export function createBaseObject(teamColor) {
  const group = new THREE.Group();
  const color = new THREE.Color(teamColor);

  const baseGeo = new THREE.CylinderGeometry(0.65, 0.75, 0.8, 6);
  const baseMat = new THREE.MeshStandardMaterial({
    color: 0xeeeeee,
    roughness: 0.4,
    metalness: 0.2
  });
  const baseMesh = new THREE.Mesh(baseGeo, baseMat);
  baseMesh.position.y = 0.4;
  baseMesh.castShadow = true;
  baseMesh.receiveShadow = true;
  group.add(baseMesh);

  const coreGeo = new THREE.CylinderGeometry(0.45, 0.45, 0.1, 6);
  const coreMat = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.9
  });
  const coreMesh = new THREE.Mesh(coreGeo, coreMat);
  coreMesh.position.y = 0.85;
  group.add(coreMesh);

  const radarGroup = new THREE.Group();
  radarGroup.position.set(0, 0.9, 0);

  const pillarGeo = new THREE.CylinderGeometry(0.08, 0.08, 0.3);
  const pillar = new THREE.Mesh(pillarGeo, baseMat);
  pillar.position.y = 0.15;
  radarGroup.add(pillar);

  const dishGeo = new THREE.ConeGeometry(0.32, 0.15, 6);
  dishGeo.rotateX(Math.PI / 4);
  const dish = new THREE.Mesh(dishGeo, baseMat);
  dish.position.set(0, 0.35, -0.1);
  dish.castShadow = true;
  radarGroup.add(dish);

  group.add(radarGroup);

  return {
    group,
    animations: [{
      update: (time) => {
        radarGroup.rotation.y = time * 1.5;
        return false;
      }
    }]
  };
}
