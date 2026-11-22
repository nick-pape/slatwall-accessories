import sys, trimesh, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
files=sys.argv[1:]
fig=plt.figure(figsize=(4*len(files),4))
for k,f in enumerate(files):
    ax=fig.add_subplot(1,len(files),k+1,projection='3d')
    m=trimesh.load(f); l=np.clip(m.face_normals@np.array([0.4,-0.6,0.7]),0.15,1)
    ax.add_collection3d(Poly3DCollection(m.triangles,facecolors=np.outer(l,[.9,.5,.2]),edgecolor='none'))
    mn,mx=m.bounds; c=(mn+mx)/2; r=(mx-mn).max()/2
    ax.set_xlim(c[0]-r,c[0]+r);ax.set_ylim(c[1]-r,c[1]+r);ax.set_zlim(c[2]-r,c[2]+r)
    ax.view_init(35,-60);ax.set_title(f.split('/')[-1]);ax.set_box_aspect((1,1,1))
plt.tight_layout();plt.savefig("preview.png",dpi=80)
