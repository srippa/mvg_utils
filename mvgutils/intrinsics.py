# AUTOGENERATED! DO NOT EDIT! File to edit: ../03_intrinsics.ipynb.

# %% auto 0
__all__ = ['SUPPORTED_CAMERA_MODELS', 'to_homogeneous', 'from_homogeneous', 'Intrinsics']

# %% ../03_intrinsics.ipynb 3
from typing import Tuple
import torch
import numpy as np
import cv2
from easydict import EasyDict as edict

# %% ../03_intrinsics.ipynb 5
SUPPORTED_CAMERA_MODELS = dict(
    SIMPLE_PINHOLE = dict(id=0, n_params=3, params_str='f, cx, cy'), 
    PINHOLE        = dict(id=1, n_params=4,params_str='fx, fy, cx, cy'), 
    SIMPLE_RADIAL  = dict(id=2, n_params=4,params_str='f, cx, cy, k'), 
    RADIAL         = dict(id=3, n_params=5,params_str='f, cx, cy, k1, k2'), 
    OPENCV         = dict(id=4, n_params=8,params_str='fx, fy, cx, cy, k1, k2, p1, p2'), 
    OPENCV_FISHEYE = dict(id=5, n_params=8,params_str='fx, fy, cx, cy, k1, k2, k3, k4'), 
    FULL_OPENCV    = dict(id=6, n_params=12,params_str='fx, fy, cx, cy, k1, k2, p1, p2, k3, k4, k5, k6'), 
    FOV            = dict(id=7, n_params=5,params_str='fx, fy, cx, cy, omega'), 
    OPENCV5        = dict(id=-1, n_params=9,params_str='fx, fy, cx, cy, k1, k2, p1, p2, k3'),
    UNKNOWN        = dict(id=-1, n_params=0,params_str='[]'), 
)

def to_homogeneous(points):
    # from https://github.com/cvg/pixloc/blob/master/pixloc/pixlib/geometry/utils.py
    """Convert N-dimensional points to homogeneous coordinates.
    Args:
        points: torch.Tensor or numpy.ndarray with size (..., N).
    Returns:
        A torch.Tensor or numpy.ndarray with size (..., N+1).
    """
    if isinstance(points, torch.Tensor):
        pad = points.new_ones(points.shape[:-1]+(1,))
        return torch.cat([points, pad], dim=-1)
    elif isinstance(points, np.ndarray):
        pad = np.ones((points.shape[:-1]+(1,)), dtype=points.dtype)
        return np.concatenate([points, pad], axis=-1)
    else:
        raise ValueError


def from_homogeneous(points):
    """Remove the homogeneous dimension of N-dimensional points.
    Args:
        points: torch.Tensor or numpy.ndarray with size (..., N+1).
    Returns:
        A torch.Tensor or numpy ndarray with size (..., N).
    """
    return points[..., :-1] / points[..., -1:]


# %% ../03_intrinsics.ipynb 6
class Intrinsics:
    'Camera intrinsic model'
    def __init__(self, 
                 camera_model_name: str,   # One of the keys in SUPPORTED_CAMERA_MODELS
                 width: int,               # width of the image in pixels
                 height: int,              # height of the image in pixels
                 params: list):            # parameters, in COLMAP conventions
        # prior_focal_length : 1 if we have confidence in the modelparameters and 0 if we do not trust the model parameters

        if camera_model_name not in SUPPORTED_CAMERA_MODELS:
            raise ValueError(f'Camera model ["{camera_model_name}"] not recognized as colmap camera model')
        
        param_names = SUPPORTED_CAMERA_MODELS[camera_model_name]['params_str'].split(',')
        param_names = [p.strip() for p in param_names]
        if len(param_names) != len(params):
            raise ValueError(f'{camera_model_name} expectes {len(param_names)} parameters but got {len(params)}') 

        self._w = width
        self._h = height

        self._camera_model_name = camera_model_name
        self._set_params(camera_model_name, params)

    @staticmethod
    def supported_camera_models():
        print('List of supported camera models and their parameters')
        print(55*'_')
        for m in SUPPORTED_CAMERA_MODELS:
            p = SUPPORTED_CAMERA_MODELS[m]['params_str']
            print(f'{m:20}: {p}')


    def __str__(self):
        s  = f'Camera: {self.camera_model_name}\n'
        s += f'  w,h={self.width,self.height}\n'
        s += f'  params: {self.params}\n'
        s += f'  cx,cy= ({self.cx},{self.cy})\n'
        s += f'  fx,fy= ({self.fx},{self.fy})\n'
        s += f'  distortions: {self.distortions}\n'


        return s

    __repr__ = __str__

    @staticmethod
    def from_pinhole_model(fx: float,   # Focal length (x) in pixels
                           fy: float,   # Focal length (y) in pixels. fy might be equal to fx (SIMPLE_PINHOLE model) or different (PINHOLE model)
                           cx:float,    # Camera center (x) in pixels
                           cy: float,   # Camera center (y) in pixels
                           width: int,  # Image width in pixels
                           height: int  # Image height in pixels
                           ) -> 'Intrinsics':
        'Contructing camera intrinsics model from opencv compatible data'
        if fx == fy:
            camera_model_name = 'SIMPLE_PINHOLE'
            params = [fx, cx, cy]
        else:
            camera_model_name = 'PINHOLE'
            params = [fx, fy, cx, cy]

        return Intrinsics(camera_model_name,width, height, params)


    @staticmethod
    def from_opencv_model(K: np.ndarray, # 3x3 camera matrix
                          distortions: np.ndarray, # distortion array as produced by OpenCv
                          width: int, # Camera width in pixels
                          height: int # Camera height in pixels
                         ) -> 'Intrinsics':
        'Contructing camera intrinsics model from opencv compatible data'
        if not isinstance(distortions, list):
            if len(distortions.shape) == 2:
                distortions = distortions.squeeze()
            distortions= distortions.tolist()
     
        fx = K[0,0]
        cx = K[0,2]
        fy = K[1,1]
        cy = K[1,2]

        params = [fx, fy, cx, cy]
        if len(distortions) == 4:
            camera_model_name = 'OPENCV'
            params += distortions
        elif len(distortions) == 5:
            camera_model_name = 'OPENCV5'
            params += distortions
        elif len(distortions) == 8:
            camera_model_name = 'FULL_OPENCV'
            params += distortions
        else:
            raise ValueError(f'Do not support opencv model with {len(distortions)} parameters')

        return Intrinsics(camera_model_name,width, height, params)

    @staticmethod
    def from_opencv_fisheye_model(K: np.ndarray, # 3x3 camera matrix
                          distortions: np.ndarray, # distortion array for OpenCv fisheye model, should consist of 4 distrortion parameters
                          width: int, # Camera width in pixels
                          height: int # Camera height in pixels
                         ) -> 'Intrinsics':
        'Contructing camera intrinsics model from data compatible with opencv fisheye model'
        if not isinstance(distortions, list):
            if len(distortions.shape) == 2:
                distortions = distortions.squeeze()
            distortions= distortions.tolist()
     
        fx = K[0,0]
        cx = K[0,2]
        fy = K[1,1]
        cy = K[1,2]

        params = [fx, fy, cx, cy]
        if len(distortions) == 4:
            camera_model_name = 'OPENCV'
            params += distortions
        else:
            raise ValueError(f'Do not support fisheye-opencv model with {len(distortions)} parameters')

        return Intrinsics(camera_model_name,width, height, params)

    @staticmethod
    def from_test_model(as_full_opencv=False):
        'Contructing camera intrinsics model from opencv calibration tutorial'
        w, h = 640, 480 

        distortions = np.array(
            [
            [-2.6637260909660682e-01], 
            [-3.8588898922304653e-02], 
            [1.7831947042852964e-03], 
            [-2.8122100441115472e-04], 
            [2.3839153080878486e-01]
            ]
        )

        if as_full_opencv:
            distortions = np.array(
                [
                [-2.6637260909660682e-01], 
                [-3.8588898922304653e-02], 
                [1.7831947042852964e-03], 
                [-2.8122100441115472e-04], 
                [2.3839153080878486e-01],
                [0.0],
                [0.0],
                [0.0]
                ]
        )

        mtx = np.array(
            [
                [5.3591573396163199e+02, 0.,                     3.4228315473308373e+02],
                [0.,                     5.3591573396163199e+02, 2.3557082909788173e+02],
                [0.,                     0.,                     1.]
            ]
        )

        return Intrinsics.from_opencv_model(mtx,distortions,w, h)

    #----------------------------------------------------------
    # Access functions
    #----------------------------------------------------------
    @property
    def camera_model_name(self) -> str:
        'Returns the name of the camera model, e.g. `OPENCV`'
        return self._camera_model_name

    @property
    def fx(self):
        'Returns the (x) focal point in pixels'
        return self._K[0,0]

    @property
    def fy(self):
        'Returns the (y) forcal point in pixels'
        return self._K[1,1]

    @property
    def cx(self):
        'Returns the x coordinate of the camera center in pixels'
        return self._K[0,2]

    @property
    def cy(self):
        'Returns the y coordinate of the camera center in pixels'
        return self._K[1,2]

    @property
    def w(self):
        'Returns the width of image, same as calling to the `width` method'
        return self._w

    @property
    def width(self):
        'Returns the width of image, same as calling to the `w` method'
        return self._w

    @property
    def h(self):
        'Returns the height of image, same as calling to the `height` method'
        return self._h

    @property
    def height(self):
        'Returns the height of image, same as calling to the `h` method'
        return self._h

    def is_single_focal_lenght(self):
        return 'SIMPLE' in self.camera_model_name

    @property
    def K(self) -> np.ndarray:
        'Return the 4x4 camera matrix in homogenous coordinates'
        return self._K

    @property
    def K_inv(self) -> np.ndarray:
        'Return the 4x4 inverse of camera matrix in homogenous coordinates'
        return self._K_inv

    @property
    def K_3(self) -> np.ndarray:
        'Return the 3x3 camera matrix in npn homogenous coordinates'
        return self._K[:3,:3]

    @property
    def K_3_inv(self) -> np.ndarray:
        'Return the 3x3 inverse of the camera matrix in npn homogenous coordinates'
        return self._K_3_inv

    @property
    def distortions(self) -> np.ndarray:
        'Returns 1D distortion array'
        return self._distortions

    def get_fov(self) -> edict:
        'Get horizontal and vertical field of view of the canera, in degrees'
        # Zeliltsky 2.60
        fovx = 2 * np.rad2deg(np.arctan2(self.width , (2 * self.fx)))
        fovy = 2 * np.rad2deg(np.arctan2(self.height , (2 * self.fy)))

        return edict(fovx=fovx, fovy=fovy)

    @property
    def params(self) -> list:
        'Get list of parametes as expected in the consrtructor for the given camera model'
        if self.is_single_focal_lenght():
            cp = [self.fx, self.cx, self.cy]
        else:
            cp = [self.fx, self.fy, self.cx, self.cy]

        p = cp + [float(d) for d in self.distortions]
        return p


    #----------------------------------------------------------
    # operations
    #----------------------------------------------------------    
    def scale(self, 
              scale_by: Tuple     #  Sacle factors as (scale_width, scale_height)
               ) -> 'Intrinsics':  # Intrinsics for  camera producing the scaled image
        'Update Intrinsicss after scaling an image '
        scale_w = scale_by[0]
        scale_h = scale_by[1]
 
        new_width = int(self.width*scale_w + 0.5)
        new_height = int(self.height*scale_h + 0.5)

        fx  = self.fx * scale_w    # fx
        fy  = self.fy * scale_h    # fy
 
        cx  = self.cx * scale_w    # cx
        cy  = self.cy * scale_h    # cy

        # COLMAP conventions
        # cx  = (self.cx+0.5) * scale_w - 0.5   # cx
        # cy  = (self.cy+0.5) * scale_h - 0.5   # cy

        new_params = self._get_params_to_new_cx_cy_fx_fy(cx, cy, fx, fy)

        return Intrinsics(
            camera_model_name=self.camera_model_name, 
            width=new_width, 
            height=new_height, 
            params=new_params
        )


    def resize(self, 
               new_size: Tuple     # New size as (new_width, new_height)
               ) -> 'Intrinsics':  # Intrinsics for the camera producing the resized image
        'Update Intrinsicss after resizing an image '
        new_width = new_size[0]
        new_height = new_size[1]
        scale_w = new_width / self.width
        scale_h = new_height / self.height
        return self.scale(scale_by=(scale_w, scale_h))

    # def crop(self, left_top: Tuple[float], size: Tuple[int]):
    # from https://github.com/cvg/pixloc/blob/65a51a7300a55d0b933dd13b6d1d7c1e6ef775d5/pixloc/pixlib/geometry/wrappers.py
    #         '''Update the camera parameters after cropping an image.'''
    #         left_top = self._data.new_tensor(left_top)
    #         size = self._data.new_tensor(size)
    #         data = torch.cat([
    #             size,
    #             self.f,
    #             self.c - left_top,
    #             self.dist], -1)
    #         return self.__class__(data)

    def crop(self, 
             top_left: Tuple[float], # Top left pixel of cropped image as (x,y)
             crop_size: Tuple[int]   # Size of cropped bbox (size_x, size_y)
             ) -> 'Intrinsics':      # Intrinsics for the camera producing the cropped image
        'Update Intrinsicss after cropping an image '

        new_cx = self.cx -  top_left[0]   
        new_cy = self.cy - top_left[1]  

        new_width = crop_size[0]
        new_height =crop_size[1]

        new_params = self._get_params_to_new_cx_cy_fx_fy(new_cx, new_cy, self.fx, self.fx)

        return Intrinsics(
            camera_model_name=self.camera_model_name, 
            width=new_width, 
            height=new_height, 
            params=new_params
        )

    #----------------------------------------------------
    # Undistrortion
    #----------------------------------------------------
    def get_undistort_camera(self, 
                             alpha: float    # A number between 0 (all pixels in the undistorted image are valid) and 1 (all source images are retained but there are some black pixels)
                             ) -> 'Intrinsics':     # A PINHOLE camera model
        'Update Intrinsicss for camera producing the undistorted image/points '
        # OpenCv function cvGetOptimalNewCameraMatrix
        #   See cvGetOptimalNewCameraMatrix in line 2714 of https://github.com/opencv/opencv/blob/4.x/modules/calib3d/src/calibration.cpp
        #   See https://docs.opencv.org/3.3.0/dc/dbb/tutorial_py_calibration.html
        # COLMAP
        #   See https://github.com/colmap/colmap/blob/dev/src/base/undistortion.h
        #     alpha is called blank_pixels

        outer, inner = self._icv_get_rectangles()

        new_image_width = self.width
        new_image_height = self.height
   
        # Projection mapping inner rectangle to viewport
        fx0 = (new_image_width-1)/ inner.width
        fy0 = (new_image_height-1)/ inner.height
        cx0 = -fx0 * inner.x
        cy0 = -fy0 * inner.y

        # Projection mapping outer rectangle to viewport
        fx1 = (new_image_width-1)/ outer.width
        fy1 = (new_image_height-1)/ outer.height
        cx1 = -fx1 * outer.x
        cy1 = -fy1 * outer.y

        # Interpolate between the two optimal projections
        fx = fx0*(1 - alpha) + fx1*alpha
        fy = fy0*(1 - alpha) + fy1*alpha
        cx = cx0*(1 - alpha) + cx1*alpha
        cy = cy0*(1 - alpha) + cy1*alpha

        new_params = [fx,fy,cx,cy]
        return Intrinsics(
            camera_model_name='PINHOLE', 
            width=new_image_width, 
            height=new_image_height, 
            params=new_params
        )
  
    def init_undistort_rectify_map(self, 
                                  alpha   # A number between 0 (all pixels in the undistorted image are valid) and 1 (all source images are retained but there are some black pixels)
                                  ) -> edict: # dict with entries: "pinhole_camera", "mapx", "mapy"
        'Return parameters needed for image undistortion plut the PINHOLE camera model of the undistorted image'
        pinhole_camera = self.get_undistort_camera(alpha)

        # See https://docs.opencv.org/3.4/da/d54/group__imgproc__transform.html#ga7dfb72c9cf9780a347fbe3d1c47e5d5a
        # code - line 64 in https://github.com/egonSchiele/OpenCV/blob/master/modules/imgproc/src/undistort.cpp
        mapx = np.zeros((pinhole_camera.h, pinhole_camera.w))
        mapy = np.zeros((pinhole_camera.h, pinhole_camera.w))

        u = list(range(pinhole_camera.w))
        v = list(range(pinhole_camera.h))
        xv, yv = np.meshgrid(u, v)
        xv = xv.reshape(pinhole_camera.h*pinhole_camera.w)
        yv = yv.reshape(pinhole_camera.h*pinhole_camera.w)
        points = np.stack([xv,yv]).T

        # Undistort all points from the pinhole camera
        p_undistorted = pinhole_camera.to_camera_points(points)  # from pinhole camera pixels to (undistorted) camera plane
        p_distorted = self.distort_points(p_undistorted)         # Distort with the distortion  model of self
        pix = self.to_image_points(p_distorted)                  # transform to image points of self

        mapx = pix[:,0].reshape((pinhole_camera.h,pinhole_camera.w))   # maping of x pixels so mapx[u,v] is the x index of that pixel in self
        mapy = pix[:,1].reshape((pinhole_camera.h,pinhole_camera.w))   # maping of y pixels so mapx[u,v] is the y index of that pixel in self

        return edict(pinhole_camera=pinhole_camera, mapx=mapx, mapy=mapy)


    #---------------------------------------------------------------------------
    # project and unproject points functions:
    #---------------------------------------------------------------------------
    # camera2image_points
    def camera2image_points(
        self, 
        pc3d: np.ndarray                                   # 3D points in camera frame system with shape (N,3)
        ) -> Tuple[np.ndarray, np.ndarray, np.ndarray] :   # A 2D point in the camera plane with shape (N,2), disparities with shape (N,1) and boolean valid mask with shape (N,)
        'Project 3D points in the camera reference coordinate system into image coordinates'

        assert(pc3d.shape[-1] == 3)

        p_camera_plane_distorted, disparity, valid = self.project_and_distort_points(pc3d)
        p_image = self.to_image_points(p_camera_plane_distorted)
        return p_image, disparity, valid

    def project_and_distort_points(
        self, 
        pc3d: np.ndarray                                   # 3D points in camera frame system with shape (N,3)
        ) -> Tuple[np.ndarray, np.ndarray, np.ndarray] :   # A 2D point in the camera plane with shape (N,2), disparities with shape (N,1) and boolean valid mask with shape (N,)
        'Project 3D points in the camera reference coordinate system into 2D distorted points in the camera frame'

        # project to camera plane (undistorted). Not used when we use OpenCV functions ProjectPoints since they project and undistort 
        # in a single function call
        p_camera_plane_undistorted, disparity, valid = self.project_points(pc3d)

        if self.camera_model_name in ['OPENCV', 'FULL_OPENCV']:
            no_rot = np.array([[0.0], [0.0], [0.0]])
            no_trans = np.array([[0.0], [0.0], [0.0]])
            K = np.eye(3)
            pimage_cv, _ =  cv2.projectPoints(
                pc3d,                              # project to image
                no_rot,
                no_trans,
                K,
                self.distortions)
            p_camera_plane_distorted = pimage_cv.squeeze(1)
        elif self.camera_model_name ==  'OPENCV_FISHEYE':
            no_rot = np.array([[0.0], [0.0], [0.0]])
            no_trans = np.array([[0.0], [0.0], [0.0]])
            K = np.eye(3)
            p_camera_plane_distorted, _ =  cv2.fisheye.projectPoints(
                pc3d,                              # project to image
                no_rot,
                no_trans,
                K,
                self.distortions)
            p_camera_plane_distorted = pimage_cv.squeeze(1)
        else:
            p_camera_plane_distorted = self.distort_points(p_camera_plane_undistorted)    

        return p_camera_plane_distorted, disparity, valid

    def project_points(
        self, 
        pc3d: np.ndarray,                                  # 3D points in camera frame, with shape (N,3) 
        projection_type: str = 'perspective'     # Projection type
        ) -> Tuple[np.ndarray, np.ndarray, np.ndarray] :   # A 2D point in the camera plane with shape (N,2), disparities with shape (N,1) and boolean valid mask with shape (N,)
        'Project 3D points in camera frame to 2D points in the camera plane'
        eps = 1e-3

        z = pc3d[..., -1]
        valid = z > eps
        z = z.clip(min=eps)
        disparity = 1.0 / np.expand_dims(z,-1)
        p2d = pc3d[..., :-1] * disparity
        return p2d, disparity, valid

    def distort_points(
        self, 
        p_cam_undistorted: np.ndarray # 2D Undistorted point in the camera plane with shape (N,2)
        ) -> np.ndarray:              # 2D distorted point in the camera plane with shape (N,2)
        'Distort points in the camera plane'
        # see line 888 in https://github.com/colmap/colmap/blob/dev/src/base/camera_models.h
        camera_model_name = self.camera_model_name
        distortions = self.distortions
        if len(distortions) == 0:
            return  p_cam_distorted.copy()


        if self.camera_model_name in ['OPENCV', 'FULL_OPENCV','OPENCV_FISHEYE']:
            raise ValueError(f'Function distort_points can not be used for OpenCv models since the do projection and distortion in a single function call, thus require 3D points as input')
        elif camera_model_name == 'SIMPLE_RADIAL':
            k1 = distortions[0]
            xd, yd = p_cam_undistorted[..., 0], p_cam_undistorted[..., 1]

            x2 = xd*xd
            y2 = yd*yd
            r2 = x2 + y2
            a = 1.0 + k1*r2  
            xu = a*xd 
            yu = a*yd 
    
            p_cam_distorted = np.stack([xu,yu], axis=-1)
            return p_cam_distorted
        elif camera_model_name == 'RADIAL':
            k1 = distortions[0]
            k2 = distortions[1]

            xd, yd = p_cam_undistorted[..., 0], p_cam_undistorted[..., 1]

            x2 = xd*xd
            y2 = yd*yd
            r2 = x2 + y2
            r4 = r2*r2

            a = 1.0 + k1*r2  + k2*r4 
            xu = a*xd 
            yu = a*yd 
    
            p_cam_distorted = np.stack([xu,yu], axis=-1)

            return p_cam_distorted
        elif camera_model_name == 'OPENCV5':
            # See https://learnopencv.com/understanding-lens-distortion/
            k1 = distortions[0]
            k2 = distortions[1]
            p1 = distortions[2]
            p2 = distortions[3] 
            k3 = distortions[4]

            xd, yd = p_cam_undistorted[..., 0], p_cam_undistorted[..., 1]

            x2 = xd*xd
            y2 = yd*yd
            xy = xd*yd
            r2 = x2 + y2
            r4 = r2*r2
            r6 = r2*r4

            a = 1.0 + k1*r2  + k2*r4 + k3*r6
            xu = a*xd + 2.0*p1*xy + p2*(r2 + 2.0*x2)
            yu = a*yd + p1*(r2+2.0*y2) + 2.0*p2*xy
    
            p_cam_distorted = np.stack([xu,yu], axis=-1)

            return p_cam_distorted
        else:
            raise ValueError(f'distort_points not impelmented for camera model [{self.camera_model_name}]')

    def to_image_points(
        self,
        pc_distorted: np.ndarray  # 2D points in the camera plane with shape (N,2)
        ) -> np.ndarray:          # 2D points in the image plane with shape (N,2)
        'Transform points from the camera plane to the image plane, using the camera matrix K'
 
        pcd_h = to_homogeneous(pc_distorted)
        pix_T = pcd_h @ self.K_3.T
        return pix_T[..., :-1]

    #----------------
    # image2camera
    #----------------
    def to_camera_points(
        self, 
        pu: np.ndarray,                  # points in the image plane, shape is (N,2)
        ) -> np.ndarray: # points in distorted camera plane, shape (N,2)
        'Transform pixel image coordinates into the distorted camera plane'
        pu_h = to_homogeneous(pu)
        pd_h_T = pu_h @ self.K_3_inv.T
        pd = pd_h_T[..., :-1]          
        return pd 


    def undistort(self, 
                  pc_distorted: np.ndarray  # Distorted points in the camera plane, shape (N,2)
                  ) -> np.ndarray:          # Undistorted points in the image plane
        'Undistort points in the image plane using the inverse of the distortion model for that camera model'
        # see line 565 in https://github.com/colmap/colmap/blob/dev/src/base/camera_models.h
        eps = np.finfo(np.float64).eps
        N = pc_distorted.shape[0]

        kNumIterations = 17
        kMaxStepNorm = np.float32(1e-10)
        kRelStepSize = np.float32(1e-6)

        J = np.zeros((N,2,2))
        p0 = pc_distorted.copy()
        x = pc_distorted.copy()
        for i in range(kNumIterations):
            x0 = x[..., 0]
            x1 = x[..., 1]
            step0 = np.maximum(eps, kRelStepSize * x0)
            step1 = np.maximum(eps, kRelStepSize * x1)

            dx = self.distort_points(x)

            # Compute numerical Jacobian
            dx_0b = self.distort_points(np.array([x0 - step0, x1]).T)
            dx_0f = self.distort_points(np.array([x0 + step0, x1]).T)
            dx_1b = self.distort_points(np.array([x0        , x1 - step1]).T)
            dx_1f = self.distort_points(np.array([x0        , x1 + step1]).T)
            J[:,0, 0] = 1 + (dx_0f[...,0] - dx_0b[...,0]) / (2 * step0)
            J[:,0, 1] = (dx_1f[...,0] - dx_1b[...,0]) / (2 * step1)
            J[:,1, 0] = (dx_0f[...,1] - dx_0b[...,1]) / (2 * step0)
            J[:,1, 1] = 1 + (dx_1f[...,1] - dx_1b[...,1]) / (2 * step1)
    
            jac_invs = np.linalg.inv(J)
            for i in range(N):
                jinv = jac_invs[i,...]
                rhs = (dx - p0)[i,:]
                sx = jinv @ rhs
                x[i,:] -= sx
 

                                                    
        return  x   # undistorted


    def _set_params(self, camera_model_name, params):
        param_names = SUPPORTED_CAMERA_MODELS[camera_model_name]['params_str'].split(',')
        param_names = [p.strip() for p in param_names]
        if len(param_names) != len(params):
            raise ValueError(f'{camera_model_name} expectes {len(param_names)} parameters but got {len(params)}') 

        self._params = params
        
        # First names should be one of f,fx,fy,cx,cy
        camera_matrix_components = ['f','fx','fy','cx','cy']
        dlist = []
        cp = edict(fx=0.,fy=0.,cx=0.,cy=0.)
        for i, (name, val) in enumerate(zip(param_names,params)):
#             print(name,val)
            if name not in camera_matrix_components:
                dlist.append(val)
            elif name == 'f': 
                cp.fx = val
                cp.fy = val
            else:
                cp[name] = val

        self._K = np.array(
            [
                [cp.fx, 0.0,     cp.cx,     0.0],
                [0.0,     cp.fy, cp.cy,     0.0],
                [0.0,     0.0,     1.0,     0.0 ],
                [0.0,     0.0,     0.0,     1.0 ]
            ]
        )
    
        self._K_inv = np.linalg.inv(self._K)
        self._K_3_inv = np.linalg.inv(self._K[:3,:3])

        self._distortions = np.array(dlist, dtype=np.float64)

    
    def _get_params_to_new_cx_cy_fx_fy(self, new_cx, new_cy, new_fx, new_fy):
        if self.is_single_focal_lenght():
            cp = [new_fx, new_cx, new_cy]
        else:
            cp =  [new_fx, new_fy, new_cx, new_cy]

        p = cp + [float(d) for d in self.distortions]
        return p


    def _icv_get_rectangles(self):
        # see icvGetRectangles, line 2460 in https://github.com/opencv/opencv/blob/4.x/modules/calib3d/src/calibration.cpp
        N = 9
        x_step = self.w / (N-1)
        y_step = self.h / (N-1)

        points = np.zeros((N*N, 2))
        k= 0
        for y in range(N):
            yp = y*y_step
            for x in range(N):
                xp = x*x_step
                points[k] = np.array([xp,yp])
                k += 1

        p_camere_distorted = self.to_camera_points(points)
        p_camera_undistorted = self.undistort(p_camere_distorted)


        k= 0
        xu_left = []
        xu_right = []
        yu_bottom = [] 
        yu_top = []         

        for y in range(N):
            yp = y*y_step
            for x in range(N):
                xp = x*x_step
                pu = p_camera_undistorted[k]
                k += 1
                if x == 0: xu_left.append(pu[0])
                if x == N-1: xu_right.append(pu[0])
                if y == 0: yu_top.append(pu[1])
                if y == N-1: yu_bottom.append(pu[1])

        pmax = np.max(p_camera_undistorted, axis=0)
        pmin = np.min(p_camera_undistorted, axis=0)
        outer = edict(x=pmin[0], y=pmin[1], width=pmax[0]-pmin[0], height=pmax[1]-pmin[1])


        xmin_i = np.max(xu_left)
        xmax_i = np.min(xu_right)
        ymin_i = np.max(yu_top)
        ymax_i = np.min(yu_bottom)
        inner = edict(x=xmin_i, y=ymin_i, width=xmax_i-xmin_i, height=ymax_i-ymin_i)

        return outer, inner

    def to_dict(self):
        return self.as_dict()

    def as_dict(self):
        asdict = dict(
            width=self.width,
            height=self.height,
            camera_model_name=self.camera_model_name,
            params=[float(p) for p in self.params.tolist()]
        )
        return asdict

#     def to_json(self, json_file):
#         write_json_file(self.as_dict(), json_file)

