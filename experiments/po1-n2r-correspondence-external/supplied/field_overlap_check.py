from pathlib import Path
import vtk, numpy as np, hashlib, json, math
from vtk.util.numpy_support import vtk_to_numpy

PO1=Path('/mnt/data/po1_art/eigenmode')
N2R=Path('/mnt/data/n2r_art/eigenmode')

def load(cycle, root):
    p=root/f'Cycle{cycle:06d}'/'proc000000.vtu'
    r=vtk.vtkXMLUnstructuredGridReader(); r.SetFileName(str(p)); r.Update(); g=r.GetOutput()
    pts=vtk_to_numpy(g.GetPoints().GetData()).astype(np.float64)
    # connectivity modern vtk
    ca=g.GetCells(); conn=vtk_to_numpy(ca.GetConnectivityArray()).astype(np.int64)
    off=vtk_to_numpy(ca.GetOffsetsArray()).astype(np.int64)
    # offsets len ncell+1; ensure tetra
    sizes=np.diff(off)
    if not np.all(sizes==4): raise RuntimeError(np.unique(sizes,return_counts=True))
    conn=conn.reshape(-1,4)
    attrs=vtk_to_numpy(g.GetCellData().GetArray('attribute')).astype(np.int32)
    Er=vtk_to_numpy(g.GetPointData().GetArray('E_real')).astype(np.float64)
    Ei=vtk_to_numpy(g.GetPointData().GetArray('E_imag')).astype(np.float64)
    E=Er+1j*Ei
    return pts,conn,attrs,E

# geometry from cycle0
Pp,Pc,Pa,_=load(0,PO1); Np,Nc,Na,_=load(0,N2R)
print('geometry exact coords',np.array_equal(Pp,Np),'conn',np.array_equal(Pc,Nc),'attrs',np.array_equal(Pa,Na))
print('max coord diff',np.max(np.abs(Pp-Np)))
print('attrs',np.unique(Pa,return_counts=True))
# volumes
x=Pp[Pc]
a=x[:,1]-x[:,0]; b=x[:,2]-x[:,0]; c=x[:,3]-x[:,0]
vol=np.abs(np.einsum('ij,ij->i',a,np.cross(b,c)))/6.0
print('vol min max sum',vol.min(),vol.max(),vol.sum())
eps=np.where(Pa==1,1.0,np.where(Pa==3,11.45,np.nan))
assert np.all(np.isfinite(eps))
w=eps*vol/20.0

# exact P1 tetra inner product: V/20 * [(sum vertices A)^*.sum(B) + sum_i A_i^*.B_i]
def inner(Ea,Eb):
    A=Ea[Pc]  # cell, vertex, comp
    B=Eb[Pc]
    sa=A.sum(axis=1); sb=B.sum(axis=1)
    term1=np.einsum('ci,ci->c',np.conj(sa),sb)
    term2=np.einsum('cvi,cvi->c',np.conj(A),B)
    return np.sum(w*(term1+term2))

fieldsP=[];fieldsN=[]
for k in range(6):
    _,_,_,E=load(k,PO1); fieldsP.append(E)
    _,_,_,E=load(k,N2R); fieldsN.append(E)

mat=np.zeros((6,6)); rms=np.zeros((6,6)); phases=np.zeros((6,6)); scales=np.zeros((6,6),dtype=complex)
for i,A in enumerate(fieldsP):
    aa=inner(A,A).real
    for j,B in enumerate(fieldsN):
        bb=inner(B,B).real
        ab=inner(B,A)  # <B,A>, c minimizing ||A-cB|| = <B,A>/<B,B>
        ov=abs(ab)/math.sqrt(aa*bb)
        copt=ab/bb
        res=max(0.0,(aa - abs(ab)**2/bb)/aa)
        mat[i,j]=ov; rms[i,j]=math.sqrt(res); scales[i,j]=copt; phases[i,j]=np.angle(copt)
np.set_printoptions(precision=9,suppress=True)
print('OVERLAP\n',mat)
print('PO1 m1 row',mat[0])
print('RMS m1 row',rms[0])
print('best by PO1')
for i in range(6):
    order=np.argsort(mat[i])[::-1]
    print(i+1,[(int(j+1),float(mat[i,j]),float(rms[i,j])) for j in order[:3]])
print('m1-m2 copt',scales[0,1], 'phase',phases[0,1], 'rms',rms[0,1])

out={'mesh':{'coords_exact':bool(np.array_equal(Pp,Np)),'connectivity_exact':bool(np.array_equal(Pc,Nc)),'attributes_exact':bool(np.array_equal(Pa,Na)),'points':len(Pp),'cells':len(Pa)},'overlap':mat.tolist(),'rms_optimal_complex_scale':rms.tolist(),'po1_m1_n2r_m2':{'overlap':float(mat[0,1]),'rms':float(rms[0,1]),'optimal_scale_real':float(scales[0,1].real),'optimal_scale_imag':float(scales[0,1].imag),'phase_rad':float(phases[0,1])}}
Path('/mnt/data/field_overlap_results.json').write_text(json.dumps(out,indent=2))
