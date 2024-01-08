"""栅格文件处理"""

import uuid

import numpy as np
import ogr
import osr
from osgeo import gdal


class RasterBlock(object):

    def __init__(self):
        self.x_id: int = 0  # x向分块编号
        self.y_id: int = 0  # y向分块编号
        self.x_offset: int = 0  # x向偏移量/像素
        self.y_offset: int = 0  # y向偏移量/像素
        self.properties = None

    def get_block_name(self):
        return "{:04d}_{:04d}.tif".format(self.x_id, self.y_id)


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
        self.x_res: float = 0  # x向分辨率
        self.y_res: float = 0  # y向分辨率
        self.extent = ()  # 四至范围 (x_min,y_min,x_max,y_max)
        self.dtype_name: str = ""  # 数据类型名称
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
        """打开文件，返回raster对象"""
        raster = Raster()
        raster.filepath = filepath
        raster.dataset = gdal.Open(filepath, gdal.GA_ReadOnly)
        raster.read_properties()
        return raster

    @staticmethod
    def create_raster(filepath, properties):
        """创建输出栅格对象"""
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
        # TODO 继承波段描述信息
        for i in range(properties.bands):
            if properties.nodata_value[i] is None:
                continue
            dataset.GetRasterBand(i + 1).SetNoDataValue(properties.nodata_value[i])
        raster.dataset = dataset

        return raster

    def read_properties(self):
        """读取栅格属性"""
        # 直接获取属性
        self.properties.width = self.dataset.RasterXSize
        self.properties.height = self.dataset.RasterYSize
        self.properties.bands = self.dataset.RasterCount
        self.properties.geotrans = self.dataset.GetGeoTransform()
        self.properties.proj = self.dataset.GetProjection()
        self.properties.dtype = self.dataset.GetRasterBand(1).DataType
        # 间接获取属性
        self.properties.dtype_name = gdal.GetDataTypeName(self.properties.dtype)
        self.properties.x_res = self.properties.geotrans[1]
        self.properties.y_res = self.properties.geotrans[5]
        self.properties.extent = (self.properties.geotrans[0],
                                  self.properties.geotrans[3],
                                  self.properties.geotrans[0] + self.properties.width * self.properties.x_res,
                                  self.properties.geotrans[3] + self.properties.height * self.properties.y_res)
        for i in range(self.properties.bands):
            self.properties.nodata_value.append(self.dataset.GetRasterBand(i + 1).GetNoDataValue())

    def read_array(self, x_offset=0, y_offset=0, x_size=None, y_size=None, band=None):
        """读取波段数据"""
        if band:
            array = self.dataset.GetRasterBand(band).ReadAsArray(xoff=x_offset, yoff=y_offset,
                                                                 win_xsize=x_size, win_ysize=y_size)
        else:
            array = self.dataset.ReadAsArray(xoff=x_offset, yoff=y_offset,
                                             xsize=x_size, ysize=y_size)
        return array

    def copy_properties(self):
        """复制栅格属性，返回properties对象"""
        properties = RasterProperties()

        properties.width = self.properties.width
        properties.height = self.properties.height
        properties.bands = self.properties.bands
        properties.geotrans = self.properties.geotrans
        properties.proj = self.properties.proj
        properties.dtype = self.properties.dtype
        properties.dtype_name = self.properties.dtype_name
        properties.x_res = self.properties.x_res
        properties.y_res = self.properties.y_res
        properties.nodata_value = self.properties.nodata_value

        return properties

    def set_array(self, array, band=None):
        """存储波段数据"""
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

    def get_block_plan(self, block_size=128, overlap=0):
        """
        对大栅格文件进行分块处理，做分块计划
        @param block_size: 分块大小
        @param overlap: 重叠率
        """
        # 计算分块信息
        overlap = overlap / 100.0
        step_x = int(block_size * (1 - overlap))
        step_y = int(block_size * (1 - overlap))
        # 计算block数量
        col_num = int(np.ceil(self.properties.width / step_x))
        row_num = int(np.ceil(self.properties.height / step_y))

        block_list = []
        for col_index in range(col_num):
            for row_index in range(row_num):
                # 创建Block对象
                block = RasterBlock()
                block.x_id = col_index + 1
                block.y_id = row_index + 1

                # 当前block偏移像素
                block.x_offset = col_index * step_x
                block.y_offset = row_index * step_y
                # 当前block实际行列
                block_width = min(block_size, self.properties.width - block.x_offset)
                block_height = min(block_size, self.properties.height - block.y_offset)

                # 创建block属性对象
                properties = self.copy_properties()
                properties.width = block_width
                properties.height = block_height
                properties.geotrans = (self.properties.geotrans[0] + block.x_offset * self.properties.x_res,
                                       self.properties.x_res,
                                       0.0,
                                       self.properties.geotrans[3] + block.y_offset * self.properties.y_res,
                                       0.0,
                                       self.properties.y_res)
                properties.extent = (properties.geotrans[0],
                                     properties.geotrans[3],
                                     properties.geotrans[0] + properties.width * properties.x_res,
                                     properties.geotrans[3] + properties.height * properties.y_res)
                block.properties = properties  # 设置属性

                # 添加到列表
                block_list.append(block)

        return block_list


if __name__ == '__main__':
    print("Finish")
