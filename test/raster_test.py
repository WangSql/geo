import os
import unittest

from Raster import Raster


class TestRaster(unittest.TestCase):

    def test_read_properties(self):
        """读取属性测试"""
        in_path = "./data/image_rgb.tif"

        raster = Raster.open_raster(in_path)
        properties = raster.properties
        print(properties)

        raster.close()

    def test_read_array(self):
        """读取数组测试"""
        in_path = "./data/image_rgb.tif"

        raster = Raster.open_raster(in_path)
        array = raster.read_array()
        array_band2 = raster.read_array(band=2)
        array_sub = raster.read_array(x_offset=512, y_offset=512, x_size=512, y_size=512)

        raster.close()

    def test_write_raster(self):
        """保存栅格测试"""
        in_path = "./data/image_rgb.tif"
        out_path = "./data/image_rgb_out.tif"

        in_raster = Raster.open_raster(in_path)
        in_array = in_raster.read_array(band=3)

        out_properties = in_raster.copy_properties()
        out_properties.bands = 1
        out_array = in_array * 1.0
        out_properties.auto_set_dtype(out_array)

        out_raster = Raster.create_raster(out_path, out_properties)
        out_raster.set_array(out_array)
        out_raster.close()

    def test_raster_block(self):
        """栅格分块"""
        in_path = "./data/image_rgb.tif"
        raster = Raster.open_raster(in_path)
        block_size = 256
        block_list = raster.get_block_plan(block_size=block_size)

        # 写出分块数据
        block_dir = os.path.join(os.path.dirname(os.path.abspath(in_path)), "block")
        if not os.path.isdir(block_dir):
            os.makedirs(block_dir)

        for i in range(len(block_list)):
            block = block_list[i]
            block_data = raster.read_array(x_offset=block.x_offset, y_offset=block.y_offset,
                                           x_size=block_size, y_size=block_size)
            out_path = os.path.join(block_dir, block.get_block_name())
            out_raster = Raster.create_raster(out_path, block.properties)
            out_raster.set_array(block_data)
            out_raster.close()
