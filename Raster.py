import uuid

import numpy as np
import ogr
import osr
from osgeo import gdal


class RasterProperties(object):
    """栅格文件常用属性类"""

    def __init__(self):
        # 直接获取
        self.width: int = 0  # 列数
        self.height: int = 0  # 行数
        self.bands: int = 0  # 波段数
        self.geotrans: tuple = ()  # 仿射矩阵
        self.proj: str = ""  # 投影信息
        self.dtype: int = 0  # 数据类型 0代表GDT_Unknown
        # 间接获取
        self.dtype_name: str = ""  # 数据类型名称
        self.cell_size: tuple = ()  # xy向分辨率
        self.nodata_value: list = []  # 各波段无效值

    def auto_set_dtype(self, np_dtype):
        """根据numpy数组类型自动设置数据类型"""
        dict_ = {
            "uint8": gdal.GDT_Byte,
            "uint16": gdal.GDT_UInt16,
            "float64": gdal.GDT_Float64,
        }
        if np_dtype.name in dict_.keys():
            self.dtype = dict_[np_dtype.name]


class Raster(object):

    def __init__(self, filepath=""):
        self.filepath: str = filepath  # 文件路径
        self.dataset = None  # gdal原生对象
        self.properties = RasterProperties()  # 封装的属性对象

    @staticmethod
    def open_raster(filepath):
        raster = Raster()
        raster.filepath = filepath
        raster.dataset = gdal.Open(filepath, gdal.GA_ReadOnly)
        raster.read_properties()
        return raster

    @staticmethod
    def create_raster(filepath, properties):
        """创建输出栅格"""
        raster = Raster()
        raster.properties = properties  # 设置栅格属性
        if filepath == "":
            mode = "MEM"
        else:
            mode = "GTiff"
        driver = gdal.GetDriverByName(mode)
        dataset = driver.Create(filepath, properties.width, properties.height, properties.bands, properties.dtype)
        dataset.SetGeoTransform(properties.geotrans)
        dataset.SetProjection(properties.proj)
        for i in range(properties.bands):
            if properties.nodata_value[i] is None:
                continue
            dataset.GetRasterBand(i + 1).SetNoDataValue(properties.nodata_value[i])
        raster.dataset = dataset

        return raster

    def read_properties(self):
        """读取属性"""
        # 直接获取属性
        self.properties.width = self.dataset.RasterXSize
        self.properties.height = self.dataset.RasterYSize
        self.properties.bands = self.dataset.RasterCount
        self.properties.geotrans = self.dataset.GetGeoTransform()
        self.properties.proj = self.dataset.GetProjection()
        self.properties.dtype = self.dataset.GetRasterBand(1).DataType
        # 间接获取属性
        self.properties.dtype_name = gdal.GetDataTypeName(self.properties.dtype)
        self.properties.cell_size = (abs(self.properties.geotrans[1]), abs(self.properties.geotrans[5]))
        for i in range(self.properties.bands):
            self.properties.nodata_value.append(self.dataset.GetRasterBand(i + 1).GetNoDataValue())

    def read_array(self, x_offset=0, y_offset=0, x_size=None, y_size=None, band=None):
        """读取数组数据"""
        if band:
            array = self.dataset.GetRasterBand(band).ReadAsArray(xoff=x_offset, yoff=y_offset,
                                                                 win_xsize=x_size, win_ysize=y_size)
        else:
            array = self.dataset.ReadAsArray(xoff=x_offset, yoff=y_offset,
                                             xsize=x_size, ysize=y_size)
        return array

    def copy_properties(self):
        properties = RasterProperties()

        properties.width = self.properties.width
        properties.height = self.properties.height
        properties.bands = self.properties.bands
        properties.geotrans = self.properties.geotrans
        properties.proj = self.properties.proj
        properties.dtype = self.properties.dtype
        properties.dtype_name = self.properties.dtype_name
        properties.cell_size = self.properties.cell_size
        properties.nodata_value = self.properties.nodata_value

        return properties

    def set_array(self, array, band=None):
        """保存数组数据"""
        if band:
            self.dataset.GetRasterBand(band).WriteArray(array)
        else:
            if len(array.shape) == 2:
                self.dataset.GetRasterBand(1).WriteArray(array)
            else:
                for i in range(self.properties.bands):
                    self.dataset.GetRasterBand(i + 1).WriteArray(array[i, :, :])

    def close(self):
        """关闭文件"""
        self.dataset = None

    def to_shapefile(self, shp_path, mask_array=None):
        """
        栅格转矢量
        @param shp_path: 输出矢量文件路径
        @param mask_array: 掩膜数组，控制转矢量的范围
        """
        mask_band = None
        if mask_array is not None:
            driver = gdal.GetDriverByName("MEM")
            mask_ds = driver.Create('', mask_array.shape[1], mask_array.shape[0], 1, gdal.GDT_Byte)
            mask_band = mask_ds.GetRasterBand(1)
            mask_band.WriteArray(mask_array)

        raster_band = self.dataset.GetRasterBand(1)

        prj = osr.SpatialReference()
        prj.ImportFromWkt(self.properties.proj)  # 读取栅格数据的投影信息
        driver = ogr.GetDriverByName("ESRI Shapefile")
        shp_ds = driver.CreateDataSource(shp_path)  # 创建一个目标文件
        layer_name = str(uuid.uuid4())
        out_layer = shp_ds.CreateLayer(layer_name, srs=prj, geom_type=ogr.wkbMultiPolygon)  # 对shp文件创建一个图层，定义为多个面类
        new_field = ogr.FieldDefn('value', ogr.OFTReal)  # 给目标shp文件添加一个字段，用来存储原始栅格的pixel value
        out_layer.CreateField(new_field)
        gdal.FPolygonize(raster_band, mask_band, out_layer, 0)  # 核心函数，执行的就是栅格转矢量操作
        shp_ds.SyncToDisk()
        shp_ds = None


if __name__ == '__main__':
    # == 读取栅格文件 == #
    in_path_ = r'C:\Users\Lenovo\Desktop\1\0001_0001_RGB.tif'
    raster1_ = Raster.open_raster(in_path_)
    array1_ = raster1_.read_array()
    array2_ = raster1_.read_array(band=2)
    properties_ = raster1_.copy_properties()
    raster1_.close()

    # == 保存栅格文件 == #
    # 写出所有波段
    # out_path_ = r'C:\Users\Lenovo\Desktop\1\0001_0001_RGB_save2.tif'
    # properties_.auto_set_dtype(array1_.dtype)
    # raster2_ = Raster.create_raster(out_path_, properties_)
    # raster2_.set_array(array1_)
    # raster2_.close()

    # 写出单波段
    out_path_ = r'C:\Users\Lenovo\Desktop\1\0001_0001_RGB_save3.tif'
    properties_.bands = 1
    array2_ = array2_ * 1.0
    properties_.auto_set_dtype(array2_.dtype)
    raster3_ = Raster.create_raster(out_path_, properties_)
    raster3_.set_array(array2_)
    raster3_.close()

    # 保存在内存中
    # raster4_ = Raster.create_raster("", properties_)
    # mask_array_ = array2_ > 100
    # array2_[array2_ < 100] = 0
    # array2_[array2_ > 100] = 255
    # raster4_.set_array(array2_)
    # # do something
    # shp_path_1 = r"C:\Users\Lenovo\Desktop\1\out.shp"
    # raster4_.to_shapefile(shp_path_1, mask_array=mask_array_)
    # raster4_.close()

    print("Finish")
