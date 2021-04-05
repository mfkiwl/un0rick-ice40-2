'''
Generate some CSR related artifacts from csr_map.yaml:
  - ../../src/rtl/csr_decoder.svh
  - ../fpga_ctrl/csr_map.md
  - ../fpga_ctrl/csr_map.py
'''

import yaml


def gen_csr_decoder_svh(csr_map):
    svh_lines = []

    # header
    svh_lines += ["// Generated by util/csr_map/gen_csr.py.\n"]
    svh_lines += ["// Please do not edit manually!\n\n"]

    # total number of CSRs
    csr_total = len(csr_map.keys())
    svh_lines += ["localparam CSR_TOTAL = %d;\n" % csr_total]
    # all CSR related parameters
    for i, csr_name in enumerate(csr_map):
        csr_data = csr_map[csr_name]
        svh_lines += ["\n// %s - %s\n" %
                      (csr_name.upper(), csr_data['description'])]
        svh_lines += ["localparam %s_ADDR = 8'h%02x;\n" %
                      (csr_name.upper(), int(csr_data['address'], 16))]
        svh_lines += ["localparam %s_POS = %d;\n" % (csr_name.upper(), i)]
        if (csr_data['type'] == 'reg'):
            svh_lines += ["localparam %s_RST = %d'h%0x;\n" %
                          (csr_name.upper(), csr_data['size'], int(csr_data['reset'], 16))]

    # header of address decoder
    svh_lines += ['''
reg [CSR_TOTAL-1:0] sel_bus;
wire [CSR_TOTAL-1:0] rvalid_bus;
wire [CSR_TOTAL*CSR_DATA_W-1:0] rdata_bus;
reg [CSR_DATA_W-1:0] csr_rdata_next;
reg csr_rvalid_next;

always @(*) begin
    csr_rdata_next  = csr_rdata;
    csr_rvalid_next = csr_rvalid;
    sel_bus         = '0;
    case (csr_addr)
''']

    # address decoder
    for csr_name in csr_map:
        csr_data = csr_map[csr_name]
        if (csr_data['type'] == 'arr'):
            for i in reversed(range(1, csr_data['length'])):
                svh_lines += ["        %s_ADDR + %d,\n" %
                              (csr_name.upper(), i)]
        svh_lines += ['''        {0}_ADDR : begin
            sel_bus[{0}_POS] = 1'b1;
            csr_rdata_next  = (csr_ren && !csr_rvalid) ? rdata_bus[{0}_POS * CSR_DATA_W +:CSR_DATA_W] : '0;
            csr_rvalid_next = (csr_ren && !csr_rvalid) ? rvalid_bus[{0}_POS] : 1'b0;
        end

'''.format(csr_name.upper())]

    # footer of adress decoder
    svh_lines += ['''    endcase
end

always @(posedge clk or posedge rst) begin
    if (rst) begin
        csr_rdata  <= '0;
        csr_rvalid <= 1'b0;
    end else begin
        csr_rdata  <= csr_rdata_next;
        csr_rvalid <= csr_rvalid_next;
    end
end
''']

    # save lines to the file
    with open('../../src/rtl/csr_decoder.vh', 'w') as file:
        file.writelines(svh_lines)


def gen_csr_map_md(csr_map):
    md_lines = []

    # header
    md_lines += ["Generated by util/csr_map/gen_csr.py.\n"]
    md_lines += ["\nPlease do not edit manually!\n\n"]

    # CSR table
    md_lines += ["|Address|Name|Size|Reset|Mode|Description|\n"]
    md_lines += ["|:-|:-|:-|:-|:-|:-|\n"]
    for csr_name in csr_map:
        csr_data = csr_map[csr_name]
        if (csr_data['type'] == 'arr'):
            for i in range(csr_data['length']):
                md_lines += ["|0x%02x|%10s%02d|%02d|%6s|%3s|%s %d|\n" % (int(csr_data['address'], 16) + i,
                                                                         csr_name.upper(), i,
                                                                         csr_data['size'],
                                                                         csr_data['reset'][i],
                                                                         csr_data['mode'],
                                                                         csr_data['description'], i)]
        else:
            md_lines += ["|%s|%12s|%02d|%6s|%3s|%s|\n" % (csr_data['address'],
                                                          csr_name.upper(),
                                                          csr_data['size'],
                                                          csr_data['reset'],
                                                          csr_data['mode'],
                                                          csr_data['description'])]
    # save lines to the file
    with open('../fpga_ctrl/csr_map.md', 'w') as file:
        file.writelines(md_lines)


def gen_csr_map_py(csr_map):
    py_lines = []

    # header
    py_lines += ["# Generated by util/csr_map/gen_csr.py.\n"]
    py_lines += ["# Please do not edit manually!\n\n"]

    py_lines += ["""class CsrMap:
    \"\"\"Control/Status register map\"\"\"
"""]

    # CSR parameters
    for csr_name in csr_map:
        csr_data = csr_map[csr_name]
        py_lines += ["\n    # %s - %s\n" %
                     (csr_name.upper(), csr_data['description'])]
        py_lines += ["    %s_ADDR = %s\n" %
                     (csr_name.upper(), csr_data['address'])]
        py_lines += ["    %s_WIDTH = %d\n" %
                     (csr_name.upper(), csr_data['size'])]
        py_lines += ["    %s_MASK = 0x%0x\n" %
                     (csr_name.upper(), (1 << csr_data['size']) - 1)]
        if (csr_data['type'] in ['arr', 'fifo']):
            py_lines += ["    %s_N = %d\n" %
                         (csr_name.upper(), csr_data['length'])]

    # init function
    py_lines += ["""
    def __init__(self, ftdidev):
        self._ftdi = ftdidev
"""]

    # reg rw string
    access_reg_rw_str = """
    @property
    def {name_lower}(self):
        \"\"\"Get current {name_upper} register value\"\"\"
        data = self._ftdi.spi_read(self.{name_upper}_ADDR, len=1, burst='fixed')
        return data[0] & self.{name_upper}_MASK

    @{name_lower}.setter
    def {name_lower}(self, val):
        \"\"\"Set {name_upper} register with new value\"\"\"
        data = val & self.{name_upper}_MASK
        self._ftdi.spi_write(self.{name_upper}_ADDR, [data], burst='fixed')
"""
    # reg ro string
    access_reg_ro_str = """
    @property
    def {name_lower}(self):
        \"\"\"Get current {name_upper} register value\"\"\"
        data = self._ftdi.spi_read(self.{name_upper}_ADDR, len=1, burst='fixed')
        return data[0] & self.{name_upper}_MASK
"""
    # reg wo string
    access_reg_wo_str = """
    @property
    def {name_lower}(self):
        \"\"\"Get current {name_upper} register value\"\"\"
        return 0

    @{name_lower}.setter
    def {name_lower}(self, val):
        \"\"\"Set {name_upper} register with new value\"\"\"
        data = val & self.{name_upper}_MASK
        self._ftdi.spi_write(self.{name_upper}_ADDR, [data], burst='fixed')
"""
    # arr rw string
    access_arr_rw_str = """
    @property
    def {name_lower}(self):
        \"\"\"Get current {name_upper} registers values\"\"\"
        data = self._ftdi.spi_read(self.{name_upper}_ADDR, len=self.{name_upper}_N, burst='incr')
        return [w & self.{name_upper}_MASK for w in data]

    @{name_lower}.setter
    def {name_lower}(self, val):
        \"\"\"Set {name_upper} registers with new values\"\"\"
        data = [w & self.{name_upper}_MASK for w in val]
        self._ftdi.spi_write(self.{name_upper}_ADDR, data, burst='incr')
"""
    # fifo ro string
    access_fifo_ro_str = """
    @property
    def {name_lower}(self):
        \"\"\"Get all data from {name_upper} buffer\"\"\"
        data = self._ftdi.spi_read(self.{name_upper}_ADDR, len=self.{name_upper}_N, burst='fixed')
        return [w & self.{name_upper}_MASK for w in data]
"""
    access_str = {'reg': {'rw': access_reg_rw_str,
                          'ro': access_reg_ro_str,
                          'wo': access_reg_wo_str},
                  'arr': {'rw': access_arr_rw_str},
                  'fifo': {'ro': access_fifo_ro_str}}
    # setters/getters
    for csr_name in csr_map:
        csr_data = csr_map[csr_name]
        csr_access_str = access_str[csr_data['type']][csr_data['mode']]
        py_lines += [csr_access_str.format(name_lower=csr_name,
                                           name_upper=csr_name.upper())]

    # save lines to the file
    with open('../fpga_ctrl/csr_map.py', 'w') as file:
        file.writelines(py_lines)


def gen_mem_init(csr_map):
    # header
    header = []
    header += ["// Generated by util/csr_map/gen_csr_map.py.\n"]
    header += ["// Please do not edit manually!\n"]

    # Create memory initialization files for every array
    for csr_name in csr_map:
        csr_data = csr_map[csr_name]
        if (csr_data['type'] == 'arr'):
            with open('../../src/rtl/%s.mem' % csr_name, 'w') as file:
                file.writelines(header)
                for i in range(csr_data['length']):
                    file.write("%x\n" % (int(csr_data['reset'][i], 16)))


if __name__ == "__main__":
    with open("csr_map.yaml", 'r') as f:
        csr_map = yaml.safe_load(f)

    gen_csr_decoder_svh(csr_map)
    gen_csr_map_md(csr_map)
    gen_csr_map_py(csr_map)
    gen_mem_init(csr_map)
