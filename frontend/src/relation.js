export const RELATION_TO_GRP = {
  엄마: 'family',
  아빠: 'family',
  형제자매: 'family',
  친구: 'friend',
}

export function resolveRelationAndGrp(form) {
  if (form.relationOption === '기타') {
    return { relation: form.customRelation.trim(), grp: form.customGrp }
  }
  return { relation: form.relationOption, grp: RELATION_TO_GRP[form.relationOption] }
}

export function isRelationValid(form) {
  return form.relationOption !== '기타' || form.customRelation.trim().length > 0
}
