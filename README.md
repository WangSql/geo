# osgeo/gdal库简化操作

1. 读取栅格文件

```python
in_path_ = 'input.tif'
raster1_ = Raster.open_raster(in_path_)
array1_ = raster1_.read_array()
array2_ = raster1_.read_array(band=2)
properties_ = raster1_.copy_properties()
raster1_.close()
```

2. 写出栅格文件

```python
out_path_ = 'output.tif'
raster2_ = Raster.create_raster(out_path_, properties_)
raster2_.set_array(array1_)
raster2_.close()
```



