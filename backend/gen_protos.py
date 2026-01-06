import os
import glob
import grpc_tools.protoc
import pkg_resources

PROTO_DIR = "vendor/investapi/proto"
GEN_DIR = "vendor/investapi/gen"


def generate_grpc():
    if not os.path.exists(GEN_DIR):
        os.makedirs(GEN_DIR)

    print(f"Scanning for protos in {PROTO_DIR}...")
    proto_files = glob.glob(f"{PROTO_DIR}/**/*.proto", recursive=True)

    if not proto_files:
        print("No proto files found!")
        exit(1)

    print(f"Found {len(proto_files)} proto files.")

    grpc_protos_include = pkg_resources.resource_filename("grpc_tools", "_proto")

    args = [
        "grpc_tools.protoc",
        f"-I{PROTO_DIR}",
        f"-I{grpc_protos_include}",
        f"--python_out={GEN_DIR}",
        f"--pyi_out={GEN_DIR}",
        f"--grpc_python_out={GEN_DIR}",
    ] + proto_files

    print("Running protoc...")
    exit_code = grpc_tools.protoc.main(args)

    if exit_code == 0:
        print("Success!")
        # Create __init__.py in all subdirectories of GEN_DIR
        for root, dirs, files in os.walk(GEN_DIR):
            init_file = os.path.join(root, "__init__.py")
            if not os.path.exists(init_file):
                with open(init_file, "w") as f:
                    f.write("# Generated gRPC code\n")
    else:
        print("Failed to generate code.")
        exit(1)


if __name__ == "__main__":
    generate_grpc()
