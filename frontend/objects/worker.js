import * as THREE from 'three';

export function createWorkerMesh(unit, teamColor, hasUnit) {
  const group = new THREE.Group();
  const bodyGeo = new THREE.SphereGeometry(0.25, 8, 8);
  const metalMat = new THREE.MeshStandardMaterial({ color: 0xdddddd, roughness: 0.3, metalness: 0.7 });
  const glowMat = new THREE.MeshBasicMaterial({ color: teamColor });

  const body = new THREE.Mesh(bodyGeo, metalMat);
  body.position.y = 0.4;
  body.castShadow = true;
  group.add(body);

  const ringGeo = new THREE.TorusGeometry(0.28, 0.05, 4, 12);
  ringGeo.rotateX(Math.PI / 2);
  const ring = new THREE.Mesh(ringGeo, glowMat);
  ring.position.y = 0.4;
  group.add(ring);

  const wingGeo = new THREE.BoxGeometry(0.12, 0.08, 0.35);
  const wingL = new THREE.Mesh(wingGeo, metalMat);
  wingL.position.set(-0.35, 0.4, 0);
  const wingR = wingL.clone();
  wingR.position.x = 0.35;
  group.add(wingL);
  group.add(wingR);

  const randomPhase = Math.random() * Math.PI * 2;
  const animation = {
    id: `bob_${unit.id}`,
    update: (time) => {
      if (!hasUnit(unit.id)) return true;
      body.position.y = 0.4 + Math.sin(time * 3.5 + randomPhase) * 0.05;
      ring.position.y = body.position.y;
      wingL.position.y = body.position.y;
      wingR.position.y = body.position.y;
      return false;
    }
  };

  return { group, animations: [animation] };
}
