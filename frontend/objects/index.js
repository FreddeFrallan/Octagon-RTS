import { createArtilleryMesh } from './artillery.js';
import { createBaseObject } from './base.js';
import { createMechMesh } from './mech.js';
import { createResourceObject } from './resource.js';
import { createWorkerMesh } from './worker.js';

const UNIT_MESH_BUILDERS = {
  artillery: createArtilleryMesh,
  mech: createMechMesh,
  worker: createWorkerMesh
};

export function createUnitObject(unit, teamColor, hasUnit) {
  const builder = UNIT_MESH_BUILDERS[unit.type] || createWorkerMesh;
  return builder(unit, teamColor, hasUnit);
}

export { createBaseObject, createResourceObject };
