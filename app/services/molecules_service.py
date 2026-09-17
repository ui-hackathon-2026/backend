"""3D conformer generation with RDKit AllChem MMFF94.

Botanical extracts resolve to a dominant marker compound before embedding,
plain molecules embed directly from SMILES. Failures raise
ConformerError, mapped to HTTP 422.
"""

from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors

MARKERS = {
    "green tea": ("Epigallocatechin Gallate", "O=C(O[C@@H]1Cc2c(O)cc(O)cc2O[C@@H]1c1cc(O)c(O)c(O)c1)c1cc(O)c(O)c(O)c1"),
    "camellia sinensis": ("Epigallocatechin Gallate", "O=C(O[C@@H]1Cc2c(O)cc(O)cc2O[C@@H]1c1cc(O)c(O)c(O)c1)c1cc(O)c(O)c(O)c1"),
    "virgin coconut oil": ("Lauric Acid", "CCCCCCCCCCCC(=O)O"),
    "cocos nucifera": ("Lauric Acid", "CCCCCCCCCCCC(=O)O"),
}


class ConformerError(ValueError):
    pass


def resolve_marker(name: str | None) -> tuple[str, str] | None:
    if not name:
        return None
    lowered = name.lower()
    for key, marker in MARKERS.items():
        if key in lowered:
            return marker
    return None


def embed(smiles: str) -> Chem.Mol:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ConformerError(f"unparseable SMILES: {smiles[:64]}")
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.useRandomCoords = True
    params.randomSeed = 0xF00D
    params.timeout = 10
    if AllChem.EmbedMolecule(mol, params) != 0:
        raise ConformerError("conformer embedding failed")
    AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
    return mol


def minimized_energy(mol: Chem.Mol) -> float | None:
    try:
        props = AllChem.MMFFGetMoleculeProperties(mol)
        field = AllChem.MMFFGetMoleculeForceField(mol, props)
        if field is None:
            return None
        return round(field.CalcEnergy(), 2)
    except Exception:
        return None


BOND_ORDERS = {
    Chem.BondType.SINGLE: 1,
    Chem.BondType.DOUBLE: 2,
    Chem.BondType.TRIPLE: 3,
    Chem.BondType.AROMATIC: 1,
}


def describe(mol: Chem.Mol, display_name: str, marker_name: str | None) -> dict:
    conf = mol.GetConformer()
    atoms = [
        {
            "id": atom.GetIdx(),
            "element": atom.GetSymbol(),
            "x": round(conf.GetAtomPosition(atom.GetIdx()).x, 4),
            "y": round(conf.GetAtomPosition(atom.GetIdx()).y, 4),
            "z": round(conf.GetAtomPosition(atom.GetIdx()).z, 4),
        }
        for atom in mol.GetAtoms()
    ]
    bonds = [
        {
            "source": bond.GetBeginAtomIdx(),
            "target": bond.GetEndAtomIdx(),
            "order": BOND_ORDERS.get(bond.GetBondType(), 1),
        }
        for bond in mol.GetBonds()
    ]
    return {
        "molecule_name": display_name,
        "marker_compound": marker_name,
        "format": "pdb",
        "pdb_content": Chem.MolToPDBBlock(mol),
        "atoms": atoms,
        "bonds": bonds,
        "molecular_weight": round(Descriptors.MolWt(mol), 2),
        "molecular_formula": Descriptors.rdMolDescriptors.CalcMolFormula(mol),
        "logP": round(Descriptors.MolLogP(mol), 2),
        "tpsa": round(Descriptors.TPSA(mol), 2),
        "h_bond_donors": Descriptors.NumHDonors(mol),
        "h_bond_acceptors": Descriptors.NumHAcceptors(mol),
        "rotatable_bonds": Descriptors.NumRotatableBonds(mol),
        "charge": 0,
        "minimized_energy_kcal_mol": minimized_energy(mol),
    }


def conformer(smiles: str | None, name: str | None) -> dict:
    marker = resolve_marker(name)
    if marker is not None:
        marker_name, marker_smiles = marker
        try:
            return describe(embed(marker_smiles), marker_name, marker_name)
        except ConformerError:
            pass
    if not smiles:
        raise ConformerError("smiles required when no marker matches")
    mol = embed(smiles)
    return describe(mol, name or smiles, None)
