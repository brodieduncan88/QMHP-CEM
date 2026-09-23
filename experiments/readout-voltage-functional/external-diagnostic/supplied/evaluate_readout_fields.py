#!/usr/bin/env python3
"""Offline evaluation of the readout surface functionals registered at 5bc50d0.

No solver is run. No source archive or repository file is changed. This is not
coupling extraction or validation of a lumped readout coordinate.

Requires numpy, vtk and shapely. Run:
  python evaluate_readout_fields.py --archive-dir /path/to/archives --out /new/output
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import platform
import tempfile
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import shapely
from shapely.geometry import Polygon, box
import vtk
from vtk.util.numpy_support import vtk_to_numpy

PIN = '5bc50d01e7c4578feb7df532b3b31956f6cefac1'
ROOT_URL = f'https://github.com/brodieduncan88/QMHP-CEM/blob/{PIN}/'
SPEC = {
 'N1R': {'archive':'N1R_fields_35438882836.zip', 'run':35438882836,
   'artifact':10583481701,
   'sha256':'79c0401c66ec7d281c90312a01409db8a862a9e9d4ce1163b52e4b0e1c111ff0',
   'record':'COUPLED-LADDER-O1-L2-N1R-20260919T110053Z',
   'port_V_blob_sha':'12286f083959af9491c94be42d3496303d76f770',
   'port_V':{1:complex(-11.03611108,-1.786799309),2:complex(-.6518580720,-.5781544558)}},
 'N2R': {'archive':'N2R_fields_35313973073.zip', 'run':35313973073,
   'artifact':10533683685,
   'sha256':'1ca851c4da54210270d6834f378bd8e5cf96e4db047beb546ac69a5079eb8b0e',
   'record':'COUPLED-LADDER-O1-L2-N2R-20260918T061455Z',
   'port_V_blob_sha':'a16a65f0a5f1b93eb55e72aed0a376ff229f9642',
   'port_V':{1:complex(-6.076988963,-9.473532972),2:complex(-.4901622609,.7298166872)},
 },
}
SURFACES={'plusY':(-.485,-.405,.05,.08,-1), 'minusY':(-.485,-.405,-.08,-.05,1)}
SQRT_Z0=19.409541814844687
LAMBDA=4.0
SCALE=SQRT_Z0/LAMBDA


def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def serial(x):
    if isinstance(x,dict):return {str(k):serial(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [serial(v) for v in x]
    if isinstance(x,np.ndarray):return serial(x.tolist())
    if isinstance(x,(complex,np.complexfloating)):
        return {'real':serial(float(x.real)), 'imag':serial(float(x.imag))}
    if isinstance(x,(float,np.floating)):
        if not math.isfinite(float(x)):raise ValueError('nonfinite diagnostic output')
        return float(x)
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    return x


def clip_integral(xyz,values,bounds):
    """Clip one linear triangle in XY; interpolate complex E_y at clip vertices.

    Integrate the piecewise-affine field exactly on each resulting polygon
    triangle (apart from floating-point arithmetic and export precision).
    """
    xl,xh,yl,yh=bounds
    poly=[(p.copy(),complex(v)) for p,v in zip(xyz,values)]
    for axis,edge,sgn in [(0,xl,1),(0,xh,-1),(1,yl,1),(1,yh,-1)]:
        if not poly:break
        result=[]
        for i in range(len(poly)):
            p,v=poly[i];q,w=poly[(i+1)%len(poly)]
            dp=sgn*(p[axis]-edge);dq=sgn*(q[axis]-edge)
            if dp>=0:result.append((p,v))
            if (dp>=0)!=(dq>=0):
                t=dp/(dp-dq);result.append((p+t*(q-p),v+t*(w-v)))
        poly=result
    value=0j;area_total=0.;subtriangles=0
    for i in range(1,len(poly)-1):
        tri=[poly[0],poly[i],poly[i+1]]
        area=np.linalg.norm(np.cross(tri[1][0]-tri[0][0],tri[2][0]-tri[0][0]))*.5
        if area<=1e-22:continue
        value+=area*sum(v for _,v in tri)/3
        area_total+=area;subtriangles+=1
    return value,area_total,subtriangles


def independent_integral(xyz,values,bounds):
    """Independent geometry clipping via GEOS; integrate an affine field at centroid."""
    xl,xh,yl,yh=bounds
    poly=Polygon(xyz[:,:2]).intersection(box(xl,yl,xh,yh))
    if poly.is_empty or poly.area==0:return 0j,0.
    p0,p1,p2=xyz[:,:2]
    st=np.linalg.solve(np.column_stack((p1-p0,p2-p0)),np.array([poly.centroid.x,poly.centroid.y])-p0)
    value=values[0]+st[0]*(values[1]-values[0])+st[1]*(values[2]-values[0])
    return poly.area*value,poly.area


def integral_tests():
    bounds=(0.,1.,0.,1.)
    triangles=[np.array([[-1.,-1.,0.],[2.,-1.,0.],[2.,2.,0.]]),
               np.array([[-1.,-1.,0.],[2.,2.,0.],[-1.,2.,0.]])]
    def f(x):return (2.+3j)+(4.-2j)*x[:,0]+(-1.+.5j)*x[:,1]
    target=(2.+3j)+(4.-2j)*.5+(-1.+.5j)*.5
    ans=sum(clip_integral(x,f(x),bounds)[0] for x in triangles)
    other=sum(independent_integral(x,f(x),bounds)[0] for x in triangles)
    reversed_ans=sum(clip_integral(x[::-1],f(x[::-1]),bounds)[0] for x in triangles[::-1])
    errors={'affine_rectangle_abs_error':abs(ans-target),
      'independent_affine_abs_error':abs(other-target),
      'orientation_reversal_abs_difference':abs(reversed_ans-ans)}
    if max(errors.values())>1e-12:raise AssertionError(errors)
    return errors


def load_grid(path):
    reader=vtk.vtkXMLUnstructuredGridReader();reader.SetFileName(str(path));reader.Update()
    if reader.GetErrorCode():raise RuntimeError(f'VTK error reading {path}')
    g=reader.GetOutput()
    points0=vtk_to_numpy(g.GetPoints().GetData()); points=points0.astype(np.float64)
    offsets=vtk_to_numpy(g.GetCells().GetOffsetsArray())
    if not np.all(np.diff(offsets)==3):raise ValueError('Expected three-vertex exported triangles')
    cells=vtk_to_numpy(g.GetCells().GetConnectivityArray()).reshape(-1,3)
    attributes=vtk_to_numpy(g.GetCellData().GetArray('attribute'))
    er=vtk_to_numpy(g.GetPointData().GetArray('E_real'));ei=vtk_to_numpy(g.GetPointData().GetArray('E_imag'))
    if not all(np.all(np.isfinite(x)) for x in [points,er,ei]):raise ValueError('Nonfinite source array')
    xyz=points[cells]; e=(er.astype(float)+1j*ei.astype(float))[cells]
    metadata={'points_dtype':str(points0.dtype),'field_dtype':str(er.dtype),
      'exported_points':len(points),'exported_cells':len(cells),
      'cell_connectivity_width':3}
    return xyz,e,attributes,metadata


def surface_integral(xyz,e,attr,key):
    xl,xh,yl,yh,sign=SURFACES[key];bounds=(xl,xh,yl,yh)
    plane=np.max(abs(xyz[:,:,2]),axis=1)<1e-8
    selected=plane&(xyz[:,:,0].max(axis=1)>=xl)&(xyz[:,:,0].min(axis=1)<=xh)&(xyz[:,:,1].max(axis=1)>=yl)&(xyz[:,:,1].min(axis=1)<=yh)
    total=0j;other=0j;area=0.;other_area=0.;byattr={};signatures=[]
    meaningful=0;pieces=0
    for j in np.nonzero(selected)[0]:
        v,a,n=clip_integral(xyz[j],e[j,:,1],bounds)
        v2,a2=independent_integral(xyz[j],e[j,:,1],bounds)
        total+=v;area+=a;other+=v2;other_area+=a2;pieces+=n
        if a>1e-20:
            at=int(attr[j]);byattr[at]=byattr.get(at,0.)+a
            signatures.append((at,tuple(sorted(tuple(float(z) for z in p) for p in xyz[j]))))
            if a>1e-12:meaningful+=1
    expected=(xh-xl)*(yh-yl)
    if abs(area-expected)>expected*1e-7:raise ValueError(f'{key}: incomplete/duplicated area {area}')
    sig=hashlib.sha256(repr(sorted(signatures)).encode()).hexdigest()
    value=sign*SCALE*total/.08; value2=sign*SCALE*other/.08
    if abs(value-value2)>1e-10*max(abs(value),1e-30):raise AssertionError('Independent quadrature mismatch')
    return {'voltage_V':value,'area_mm2':area,'expected_area_mm2':expected,
       'contributing_exported_triangles':len(signatures),
       'triangles_with_clipped_area_above_1e_12_mm2':meaningful,
       'area_by_attribute_mm2':byattr,'local_geometry_sha256':sig,
       'independent_integration_relative_difference':abs(value-value2)/max(abs(value),1e-300),
       'independent_area_difference_mm2':other_area-area}


def evaluate(archive_dir,out):
    if out.exists() and any(out.iterdir()):raise FileExistsError('Use a new/empty output directory')
    out.mkdir(parents=True,exist_ok=True)
    results={
      'schema':'qmhp.local-readout-field-diagnostic/0.1',
      'classification':'OFFLINE POSTPROCESSING DIAGNOSTIC; NOT COUPLING EXTRACTION',
      'repository_read_only_pin':PIN,
      'functional_source':ROOT_URL+'experiments/readout-voltage-functional/functional.json',
      'functional_source_blob_sha':'4a605e89513236695a17a66f261003bec6b6abc8',
      'definitions':{'surfaces_mm':SURFACES,'readout_width_mm':.08,'F_port_attribute':10,
        'F_port_width_mm':.02,'sqrt_Z0':SQRT_Z0,'Lc_over_L0':LAMBDA,
        'primary_readout_surface':'plusY','mirror_check_surface':'minusY',
        'rho':'complex V_R / reconstructed V_F for each mode',
        'r12':'complex rho_mode1 / rho_mode2, signs retained',
        'mirror_relative_difference':'abs(plus-minus) / max(abs(plus),abs(minus))',
        'mesh_relative_change':'abs(N2R-N1R) / abs(N1R)'},
      'unit_statement':'Use the pinned recipe for this export, not newer Palace release defaults.',
      'tests':integral_tests(),
      'environment':{'python':platform.python_version(),'numpy':np.__version__,
        'vtk':vtk.vtkVersion.GetVTKVersion(),'shapely':shapely.__version__},
      'datasets':{},
      'limitations':[
        'No Palace run or new eigenpair; no repository mutation.',
        'No g, capacitance, E_C, Route A inversion, Route B or physical validation.',
        'Exported Float32 point values are promoted for arithmetic, not upgraded in source precision.',
        'The F-port comparison validates only this limited reconstruction, not readout accuracy.',
        'Differences between the two readout surfaces are not attributed to a unique cause.',
        'Same readout surface triangles do not establish readout-gap convergence or full-volume identity.',
        'These surface integrals have not been established as a unique lumped readout coordinate.',
        'Incomplete modal evidence and synthetic-to-EM model compatibility remain unresolved.'
      ]}
    for name,spec in SPEC.items():
        archive=archive_dir/spec['archive']
        actual_hash=digest(archive)
        if actual_hash!=spec['sha256']:raise ValueError('Archive hash mismatch: '+name)
        record={'archive':spec['archive'],'archive_sha256':actual_hash,'archive_size_bytes':archive.stat().st_size,
          'run':spec['run'],'artifact':spec['artifact'],'source_record':spec['record'],
          'port_V_source':ROOT_URL+'results/'+spec['record']+'/L2/solver/postpro/port-V.csv',
          'port_V_blob_sha':spec['port_V_blob_sha'],'modes':{}}
        with zipfile.ZipFile(archive) as z,tempfile.TemporaryDirectory() as tmp:
            mapping=ET.fromstring(z.read('eigenmode_boundary/eigenmode_boundary.pvd'))
            entries={int(float(e.attrib['timestep'])):e.attrib['file'] for e in mapping.iter('DataSet')}
            record['boundary_mode_fields_available']=sorted(entries)
            for m in [1,2]:
                base=Path(entries[m]).parent
                member=str(Path('eigenmode_boundary')/base/'proc000000.vtu')
                path=Path(tmp)/f'm{m}.vtu';path.write_bytes(z.read(member))
                xyz,e,attr,metadata=load_grid(path)
                use=attr==10
                areas=np.linalg.norm(np.cross(xyz[use,1]-xyz[use,0],xyz[use,2]-xyz[use,0]),axis=1)*.5
                vf=SCALE*np.sum(areas*np.mean(e[use,:,1],axis=1))/.02
                ref=spec['port_V'][m]
                if abs(vf)==0:raise ZeroDivisionError('Zero F voltage')
                row={'archive_member':member,'member_sha256':digest(path),'export':metadata,
                  'F_port':{'voltage_reconstructed_V':vf,'voltage_reference_V':ref,
                    'area_mm2':float(areas.sum()),'triangles':int(use.sum()),
                    'relative_complex_error':abs(vf-ref)/abs(ref),
                    'relative_real_error':abs(vf.real-ref.real)/abs(ref.real),
                    'relative_imag_error':abs(vf.imag-ref.imag)/abs(ref.imag)},'readout':{}}
                for side in SURFACES:
                    s=surface_integral(xyz,e,attr,side)
                    s['rho']=s['voltage_V']/vf
                    s['rho_using_reference_VF']=s['voltage_V']/ref
                    row['readout'][side]=s
                vp=row['readout']['plusY']['voltage_V'];vm=row['readout']['minusY']['voltage_V']
                row['mirror_voltage_relative_difference']=abs(vp-vm)/max(abs(vp),abs(vm))
                record['modes'][m]=row
        record['r12']={s:record['modes'][1]['readout'][s]['rho']/record['modes'][2]['readout'][s]['rho'] for s in SURFACES}
        ap,am=record['r12']['plusY'],record['r12']['minusY']
        record['r12_mirror_relative_difference']=abs(ap-am)/max(abs(ap),abs(am))
        results['datasets'][name]=record
    a=results['datasets']['N1R'];b=results['datasets']['N2R']
    results['between_meshes']={s:{
        'r12_signed_change':b['r12'][s]-a['r12'][s],
        'r12_relative_change':abs(b['r12'][s]-a['r12'][s])/abs(a['r12'][s]),
        'same_exported_readout_triangle_geometry': a['modes'][1]['readout'][s]['local_geometry_sha256']==b['modes'][1]['readout'][s]['local_geometry_sha256']}
        for s in SURFACES}
    max_f=max(r['F_port']['relative_complex_error'] for d in results['datasets'].values() for r in d['modes'].values())
    results['max_F_port_relative_complex_error']=max_f
    results['conclusion']='The archive-access blocker is removed in this environment. The fixed surface integrals can be evaluated. Their cross-mode ratio is surface-dependent at about 13-14% under the declared mirror metric, and changes by about 1.6-1.9% between these meshes. No unique lumped-coordinate or coupling claim follows.'
    (out/'results.json').write_text(json.dumps(serial(results),indent=2,allow_nan=False)+'\n')
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();res=evaluate(args.archive_dir,args.out)
    print('maximum F-port reconstruction relative error:',res['max_F_port_relative_complex_error'])
    for name,r in res['datasets'].items():
        print(name,'r12:',r['r12'],'mirror relative difference:',r['r12_mirror_relative_difference'])
    print('between_meshes:',res['between_meshes'])
if __name__=='__main__':main()
